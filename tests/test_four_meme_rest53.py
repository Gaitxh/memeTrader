import asyncio
from types import SimpleNamespace
import httpx
from memetrader.four_meme_rest import FourMemeRestObserver

def test_bounded_listing_provenance_and_progress():
    calls=[]
    row=dict(tokenAddress="0x"+"1"*40, networkCode=0,status="PUBLISH",name="T",shortName="T",progress="0",price="999",createDate="123")
    class Client:
        async def post(self,url,**kw):
            calls.append(kw)
            return httpx.Response(200,json={"code":0,"data":[row,dict(row,status="INIT"),dict(row,networkCode=1)]+[row]*40},request=httpx.Request("POST",url))
    async def run():
        o=FourMemeRestObserver(SimpleNamespace(client=Client()))
        results=[await o.observe() for _ in range(3)]
        assert [c["json"]["type"] for c in calls]==["NEW","NEW","PROGRESS"]
        for r in results:
            assert len(r["events"])<=30
            e=r["events"][0]
            assert e["evidence_kind"]=="official_native_listing" and not e["buy_authority"]
            assert "price_usd" not in e and "transaction_hash" not in e
            assert e["observed_at"]!=e["published_at_ms"]
        assert results[0]["events"][0]["source_key"]==results[2]["events"][0]["source_key"]
    asyncio.run(run())

def test_rate_limit_is_error_not_empty_success():
    class Client:
        async def post(self,url,**kw):
            return httpx.Response(429,request=httpx.Request("POST",url))
    r=asyncio.run(FourMemeRestObserver(SimpleNamespace(client=Client())).observe())
    assert r["status"]=="ERROR" and not r["events"]
