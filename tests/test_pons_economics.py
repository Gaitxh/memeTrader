from datetime import datetime, timezone, timedelta
from decimal import Decimal
import asyncio
import pytest
from memetrader.pons_economics import roundtrip, usd_conversion, PonsEconomicsObserver


def state(**kwargs):
    return dict(reserves=[100000,1000000],real=100000,sellable=900000,
                fee=100,creator=500,snipe=0,ready=0,graduated=0,**kwargs)


def test_post_buy_reserves_and_fee_rounding():
    r=roundtrip(state(),5,Decimal(1),Decimal(1),3)
    assert r['token_out_raw']=='44890'
    assert r['quote_recovered_raw']=='4419'  # gross4699 - floor46.99 - floor234.95
    # Quoting against the old reserves would produce a different, false recovery.
    assert int(r['quote_recovered_raw']) > (44890*100000//1044890)*94//100
    assert r['status']=='MODEL_QUOTE'


def test_snipe_and_graduation():
    a=state();a['snipe']=9900
    assert Decimal(roundtrip(a,5,Decimal(1),Decimal(1),3)['sell_usd']) < 1
    a=state();a['sellable']=100
    r=roundtrip(a,5,Decimal(1),Decimal(1),3)
    assert r['status']=='SELL_UNAVAILABLE' and 'sell_usd' not in r


def test_conversion_identity_multiplier_clock():
    now=datetime.now(timezone.utc);d=[dict(chainId=4663,contractAddress='0xabc')]
    a=dict(deployments=d,tokenSymbol='X',currentMultiplier='2',status='ASSET_STATUS_ACTIVE')
    q=dict(deployments=d,tokenSymbol='X',bid='3',ask='4',currency='USD',isTradingHalt=False,generatedAt=now.isoformat())
    assert usd_conversion(a,q,'0xabc',now)==(Decimal(6),Decimal(8))
    for change in [dict(generatedAt=(now+timedelta(seconds=1)).isoformat()),dict(currency='ETH'),dict(isTradingHalt=True)]:
        with pytest.raises(ValueError):usd_conversion(a,{**q,**change},'0xabc',now)
    with pytest.raises(ValueError):usd_conversion(a,q,'0xdef',now)


def test_held_defer_without_any_request():
    from memetrader.pons_observer import PonsV2Observer
    o=PonsEconomicsObserver(None,None)
    r=asyncio.run(o.observe(dict(token='x',curve='y',pair_token='z',factory=PonsV2Observer.FACTORY,event='TokenLaunched'),lambda:True))
    assert r['reason']=='held_priority_deferred'
    assert r['decision_eligible'] is False and r['affects']=='none'


def test_evidence_state_time_separate_from_local_availability():
    from memetrader.pons_economics import evidence_observed_at
    r=dict(status='OBSERVED',observed_at='2026-09-09T05:00:00+00:00',
           ingested_at='2026-09-09T05:00:02+00:00',recorded_at='2026-09-09T05:00:03+00:00')
    assert evidence_observed_at(r)==r['observed_at']
    assert evidence_observed_at({**r,'status':'UNKNOWN'})==r['recorded_at']
    with pytest.raises(ValueError):
        evidence_observed_at({**r,'ingested_at':'2026-09-09T04:59:59+00:00'})


def test_factory_event_does_not_substitute_for_instance_semantics():
    from memetrader.pons_observer import PonsV2Observer
    class Response:
        def json(self): return {}
    class Http:
        async def get(self,*args,**kwargs): return Response()
    r=asyncio.run(PonsEconomicsObserver(None,Http()).observe(dict(token='0x1',curve='0x2',
        pair_token='0x3',factory=PonsV2Observer.FACTORY,event='TokenLaunched')))
    assert r['status']=='UNKNOWN' and r['reason']=='unverified_curve_source_version'
    assert 'quotes' not in r


def test_native_quote_unknown_without_stock_lookup():
    from memetrader.pons_observer import PonsV2Observer
    r=asyncio.run(PonsEconomicsObserver(None,None).observe(dict(token='0x1',curve='0x2',
        pair_token='0x'+'0'*40,factory=PonsV2Observer.FACTORY,event='TokenLaunched')))
    assert r['reason']=='UNSUPPORTED_QUOTE_NATIVE_ETH_USD_NOT_PROVEN'
    assert r['status']=='UNKNOWN'


def test_every_launch_enrolled_busy_rotation_restart_and_expiry():
    from memetrader.pons_economics import PonsEconomicsEnrollment
    now=datetime.now(timezone.utc)
    q=PonsEconomicsEnrollment()
    for i in range(6):
        e=dict(curve=hex(i+1),token=hex(i+10))
        assert q.enroll(e,now)['status']=='ENROLLED'
        assert q.enroll(e,now) is None
    class Observer:
        calls=0
        async def observe(self,e,busy):
            self.calls+=1
            return dict(status='UNKNOWN',reason='proof_missing',recorded_at=now.isoformat())
    o=Observer()
    assert asyncio.run(q.step(o,lambda:True,now))==[]
    assert len(q.pending)==6 and o.calls==0 and q.pending[0]['status']=='DEFERRED_BUSY'
    q=PonsEconomicsEnrollment(q.snapshot())
    assert len(asyncio.run(q.step(o,lambda:False,now+timedelta(seconds=150))))==1
    assert o.calls==1 and len(q.pending)==5
    assert len(asyncio.run(q.step(o,lambda:False,now+timedelta(minutes=16))))==5
    assert o.calls==1 and not q.pending and q.counts['EXPIRED_UNATTEMPTED']==5
    assert q.counts['launch']==6 and q.counts['attempted']==1


def test_enrollment_bound_is_explicit_not_silent():
    from memetrader.pons_economics import PonsEconomicsEnrollment
    q=PonsEconomicsEnrollment();now=datetime.now(timezone.utc)
    for i in range(33):r=q.enroll(dict(curve=hex(i),token=hex(i)),now)
    assert r['status']=='DEFERRED_CAPACITY' and len(q.pending)==32
    assert q.counts['launch']==33 and q.counts['enrolled']==32


def test_runtime_drains_only_existing_pons_rotation_and_propagates_cancel():
    from types import SimpleNamespace
    from memetrader.runtime import Runtime
    from memetrader.pons_observer import PonsV2Observer
    from memetrader.pons_economics import PonsEconomicsEnrollment
    r=Runtime.__new__(Runtime)
    r._native_launch_observers=[object(), PonsV2Observer.__new__(PonsV2Observer)]
    r._native_launch_cursor=0
    r._pons_economics_enrollment=PonsEconomicsEnrollment()
    q=r._pons_economics_enrollment
    q.enroll(dict(curve='0x1',token='0x2',token_id='robinhood:0x2'),datetime.now(timezone.utc))
    class Observer:
        calls=0
        async def observe(self,event,busy):
            self.calls+=1
            return dict(status='UNKNOWN',reason='proof_missing',recorded_at=datetime.now(timezone.utc).isoformat())
    r._pons_economics=Observer()
    records=[]
    r.store=SimpleNamespace(set_kv=lambda *a:None,record_chain_meme_pattern_evidence=lambda *a,**k:records.append(a))
    r._critical_onchain_exit_event=asyncio.Event()
    r._evm_route_quote_lock=asyncio.Lock()
    idle=asyncio.Event();idle.set()
    r._chain_meme_active_idle=lambda:idle
    async def tick():pass
    r._chain_meme_native_launch_observe_once=tick
    asyncio.run(r.chain_meme_native_launch_once())
    assert r._pons_economics.calls==0
    r._native_launch_cursor=1
    async def cancelled():raise asyncio.CancelledError()
    r._chain_meme_native_launch_observe_once=cancelled
    with pytest.raises(asyncio.CancelledError):asyncio.run(r.chain_meme_native_launch_once())
    assert r._pons_economics.calls==0
    r._chain_meme_native_launch_observe_once=tick
    asyncio.run(r.chain_meme_native_launch_once())
    assert r._pons_economics.calls==1 and len(records)==1 and not q.pending
