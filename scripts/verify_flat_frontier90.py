"""One read-only, consistent production-snapshot equivalence/latency check."""
import json
from pathlib import Path
import sqlite3
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
from memetrader.models import utcnow, iso
from memetrader.store import Store
from memetrader.flat_selector import FlatSelector

path=Path('data/memetrader_forward_20260830_r6.sqlite3').resolve()
db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
db.row_factory=sqlite3.Row
db.execute('BEGIN')
cutoff=utcnow()
start=time.perf_counter()
db.set_progress_handler(lambda:int(time.perf_counter()-start>60),10000)
class Shared:
    def __init__(self):self.row_factory=sqlite3.Row
    def execute(self,sql,*args):
        if sql=='BEGIN':return db.execute('SELECT 1')
        return db.execute(sql,*args)
    def close(self):pass
store=SimpleNamespace(path=path,db=db,_lock=threading.RLock(),
    CHAIN_MEME_TRADER_ACTIVE_VERSION=Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
    FLAT_BREAKOUT_SHADOW_VERSION=Store.FLAT_BREAKOUT_SHADOW_VERSION)
t=time.perf_counter()
baseline=Store.due_flat_compression_breakout_shadow_targets(store,now=cutoff,connection=db)
baseline_seconds=time.perf_counter()-t
selector=FlatSelector(store)
with patch('memetrader.flat_selector.sqlite3.connect',lambda *a,**k:Shared()):
    t=time.perf_counter();initial=selector.due_targets(now=cutoff);initial_seconds=time.perf_counter()-t
    assert initial==baseline,(initial,baseline)
    repeat=[]
    for _ in range(5):
        t=time.perf_counter();result=selector.due_targets(now=cutoff);repeat.append(time.perf_counter()-t)
        assert result==baseline
out=dict(cutoff=iso(cutoff),baseline_seconds=baseline_seconds,bootstrap_seconds=initial_seconds,
    repeated_seconds=repeat,ordered_equal=True,targets=baseline,
    evaluation_frontier=selector._evaluation_frontier,observation_frontier=selector._observation_frontier,
    candidate_count=len(selector._frontier._targets),readonly=True)
db.close()
dest=Path('data/research/system90');dest.mkdir(parents=True,exist_ok=True)
(dest/'flat_equivalence.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='targets'}))
