import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('first_hit75',Path(__file__).resolve().parents[1]/'scripts/research_first_hit75.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def frame(i,t,net):
    return dict(id=i,obs=t,rec=t+1,price=(1+net)*1.04/.96)

def test_stop_then_moon_is_not_positive_first():
    entry=dict(id=0,obs=0,rec=1,price=1)
    r=m.walk(entry,[frame(1,20,-.3),frame(2,40,1.2)])
    assert r['order100']=='STOP_FIRST' and r['order30']=='STOP_FIRST'
    assert r['replay']['signal_id']==1 and r['replay']['fill_id']==2

def test_gap_unknown_and_no_cached_clock_replay():
    entry=dict(id=0,obs=0,rec=1,price=1)
    r=m.walk(entry,[frame(1,1,2),frame(2,200,1.2)])
    assert r['hits']['up100']['id']==2 and r['order100']=='UNKNOWN_GAP'

def test_positive_then_stop_order():
    entry=dict(id=0,obs=0,rec=1,price=1)
    r=m.walk(entry,[frame(1,20,.4),frame(2,40,-.3),frame(3,60,1.2)])
    assert r['order30']=='POSITIVE_FIRST' and r['order100']=='STOP_FIRST'
