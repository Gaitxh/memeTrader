import asyncio
from types import SimpleNamespace
import httpx
from memetrader.launchlab_observer import LaunchLabObserver

MINT = "CA5PgaUP5oCQXnbW155WZXjJSZfVd2wvGR4oXfcoSTNK"
POOL = "GxcGUUj7xriDNDmr3CueM2xNrEmyyYLqswASdSqk25x8"

def test_causal_new_identity_only_and_no_quote_authority():
    async def run():
        data = {"success": True, "data": {"rows": []}}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=data))) as client:
            observer = LaunchLabObserver(SimpleNamespace(client=client))
            row = dict(mint=MINT,poolId=POOL,createAt=observer.activation_ms-1,finishingRate=0.5)
            data['data']['rows']=[row]
            assert not (await observer.observe())['events']
            observer.seen.clear()
            row['createAt']=observer.activation_ms
            event=(await observer.observe())['events'][0]
            assert event['pool']==POOL and event['token']==MINT
            assert not event['buy_authority'] and not event['finality']
            assert 'price_usd' not in event and event['raw']['finishingRate']==0.5
            assert not (await observer.observe())['events']
    asyncio.run(run())

def test_invalid_identity_future_time_and_provider_error():
    async def run():
        data={"success":True,"data":{"rows":[]}}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=data))) as client:
            observer=LaunchLabObserver(SimpleNamespace(client=client))
            data['data']['rows']=[dict(mint=MINT,poolId=POOL,createAt=observer.activation_ms+3600000),dict(mint='bad',poolId=POOL,createAt=observer.activation_ms)]
            assert not (await observer.observe())['events']
            data['success']=False
            assert (await observer.observe())['status']=='ERROR'
    asyncio.run(run())
