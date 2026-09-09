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
