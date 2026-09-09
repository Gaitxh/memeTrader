from datetime import timedelta
from copy import deepcopy
from memetrader.models import utcnow,iso,TokenCandidate
from memetrader.clone_consensus_outcomes import CloneConsensusOutcomes
from test_paper_execution import _snapshot


def setup():
    s=CloneConsensusOutcomes();now=utcnow();token=TokenCandidate('robinhood','0x'+'12'*20,'C','C');pool='0x'+'34'*20
    anchor=dict(eligible=True,price_usd=1.,observed_at=iso(now),ingested_at=iso(now),recorded_at=iso(now),provider='test')
    s.capture_signal(1,token.token_id,pool,anchor,{},now)
    return s,now,token,pool


def test_horizon_floor_order_exact_pool_restart_and_expiry():
    s,t,token,pool=setup()
    def frame(sec,price,liq,pair=pool):
        at=t+timedelta(seconds=sec);snap=_snapshot(token,pair,at);snap.price_usd=price;snap.liquidity_usd=liq
        s.observe(token.token_id,snap,at,at)
    frame(1,1.,500)
    frame(900,5.,50000,'0x'+'56'*20)
    row=next(iter(s.state['pending'].values()));assert not row['results']
    frame(901,2.,50000)
    result=row['results']['15'];assert result['status']=='OBSERVED' and result['path_order']=='FLOOR_FIRST'
    assert result['raw_return']==1 and result['paper_cost_estimated_return']<1
    assert all(k in result for k in ['observed_at','ingested_at','recorded_at'])
    restored=CloneConsensusOutcomes(deepcopy(s.snapshot()))
    restored.expire(t+timedelta(minutes=246))
    assert len(restored.state['recent'])==1
    assert restored.state['recent'][0]['results']['60']['status']=='UNKNOWN'
    assert restored.state['floor_episodes']==1


def test_duplicate_clock_does_not_resolve_and_capacity_is_bounded():
    s,t,token,pool=setup();row=next(iter(s.state['pending'].values()))
    at=t+timedelta(minutes=15);snap=_snapshot(token,pool,t)
    s.observe(token.token_id,snap,at,at)
    assert row['results']=={}
    for i in range(1,140):s.capture_signal(i,token.token_id,pool,row['anchor'],{},t)
    assert len(s.state['pending'])==128 and s.state['capacity_skipped']==11
    s.expire(t+timedelta(minutes=246))
    assert len(s.state['recent'])==128 and not s.state['pending']
