"""One read-only model probe; research artifact only, no production write."""
import asyncio,json,time
from pathlib import Path
from memetrader.collectors import HttpClient,EvmUniswapV3QuoteClient
from memetrader.pons_observer import PonsV2Observer
from memetrader.pons_economics import PonsEconomicsObserver

async def main():
    h=HttpClient(timeout=4,min_host_interval=.6)
    try:
        e=dict(token='0x7e9e1f2f748b58a16dad7afd5b1f207ed3e1bfa4',curve='0x25d3708b0c93f312a72002a7f8ebd92b04d3eb41',
               pair_token='0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec',factory=PonsV2Observer.FACTORY,event='TokenLaunched')
        observer=PonsEconomicsObserver(EvmUniswapV3QuoteClient(h),h)
        # Already retrieved proof, verified before this current-state probe; no new bypass request.
        proof=Path(__file__).resolve().parents[1]/'data/research/native74/verified_curve.json'
        observer.verified_cache[e['curve']]=json.loads(proof.read_text(encoding='utf-8'))
        t=time.monotonic();r=await observer.observe(e)
        r['elapsed']=time.monotonic()-t
        p=Path(__file__).resolve().parents[1]/'data/research/native74/economics_probe.json'
        p.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r))
    finally:await h.client.aclose()
asyncio.run(main())
