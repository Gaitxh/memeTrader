import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from research_today23_78 import valid,ADDRESSES

def sample(**changes):
 p=dict(pairAddress='0xABC',chainId='bsc',baseToken=dict(address='0x123'),txns=dict(m5=dict(buys=0)),volume={})
 r=dict(id=1,token_id='bsc:0x123',observed_at='2026-09-09T00:00:00Z',ingested_at='2026-09-09T00:00:01Z',recorded_at='2026-09-09T00:00:02Z',price_usd=1,liquidity_usd=500,provider='geckoterminal',raw_json=json.dumps(dict(pair=p)))
 r.update(changes);return r

def test_identity_clock_and_floor_evidence():
 assert valid(sample())['liq']==500
 assert valid(sample(token_id='bsc:0x124')) is None
 assert valid(sample(observed_at='2026-09-09T00:00:03Z')) is None
 assert valid(sample(recorded_at='2026-09-09T06:50:00Z')) is None

def test_missing_is_not_zero_and_exact_case_list():
 f=valid(sample());assert f['buys']==0 and f['sells'] is None and f['volume'] is None
 assert len(ADDRESSES)==len(set(ADDRESSES))==23
