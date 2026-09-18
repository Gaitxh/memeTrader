"""Telemetry publication optimization must preserve every reported percentile."""
from collections import deque
import builtins
import random
import pytest
import memetrader.runtime_timing as m

@pytest.mark.parametrize('size',[0,1,2,3,17,120])
def test_shared_sort_matches_single_quantile_api_without_mutation(size):
    rng=random.Random(238)
    values=deque((rng.random()*100 for _ in range(size)),maxlen=120)
    before=list(values)
    expected={k:m._percentile(values,q) for k,q in
              (('p50',.5),('p90',.9),('p95',.95),('p99',.99))}
    assert m._percentiles(values)==expected
    assert list(values)==before

def test_interpolation_and_repeated_values():
    assert m._percentiles(deque([0.,10.]))==pytest.approx(
        {'p50':5.,'p90':9.,'p95':9.5,'p99':9.9})
    assert set(m._percentiles(deque([2.,2.,2.])).values())=={2.}

def test_single_sort_for_all_four_quantiles(monkeypatch):
    calls=[]
    def counted(values):
        calls.append(1)
        return builtins.sorted(values)
    monkeypatch.setattr(m,'sorted',counted,raising=False)
    assert m._percentiles(deque([3.,1.,2.]))['p50']==2.
    assert len(calls)==1

def test_snapshot_retains_activity_queue_counts_and_samples():
    timer=m.RuntimeTiming()
    for n in range(150):
        timer.observe('worker',n/10,interval_seconds=2.,items=3,failures=int(n==0))
        timer.observe_passive_queue(depth=0,oldest_received_at=None,wait_seconds=n/100)
    snap=timer.snapshot(); component=snap['components']['worker']
    assert component['sample_count']==120
    assert component['items']==450 and component['failures']==1
    assert snap['activity']['worker']=={'calls':150,'items':450,'failures':1}
    assert snap['passive_queue']['processed_batches']==150
    assert snap['passive_queue']['wait_sample_count']==120
    assert component['duration_seconds']==m._percentiles(deque(n/10 for n in range(30,150)))
    assert snap['passive_queue']['wait_seconds']==m._percentiles(deque(n/100 for n in range(30,150)))
