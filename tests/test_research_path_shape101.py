import importlib.util
import math
from pathlib import Path

spec=importlib.util.spec_from_file_location('shape101',Path(__file__).parents[1]/'scripts/research_path_shape101.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def frames(prices):
    return [dict(id=i,obs=i*20,rec=i*20+1,price=p,liq=1000) for i,p in enumerate(prices)]


def test_linear_is_shape_not_scam():
    f,state=m.shape(frames([math.exp(i*.02) for i in range(8)]))
    assert state=='LINEAR_RATCHET' and abs(f['robust_r2']-1)<1e-10
    assert f['liquidity_price_correlation'] is None


def test_flat_not_linear_and_staircase():
    assert m.shape(frames([1]*8))[1]=='NORMAL'
    assert m.shape(frames([1,1,1.05,1.05,1.1,1.1,1.15,1.15]))[1]=='STAIRCASE_RATCHET'


def test_causal_reject_same_generation_and_availability_overlap():
    ss=frames([1,2,3]);ss[1]['obs']=ss[0]['rec']
    assert [s['id'] for s in m.causal(ss)]==[0,2]


def test_first_hit_stop_then_tail_are_not_exclusive():
    e=dict(id=0,obs=0,rec=1,price=1,liq=1000)
    ss=[dict(id=1,obs=20,rec=21,price=.5,liq=1000),dict(id=2,obs=40,rec=41,price=3,liq=1000)]
    o=m.outcome(e,ss,900)
    assert o['tail100'] and o['loss50'] and o['first_hit']=='STOP_FIRST'
    assert o['endpoint'] is None


def test_gap_and_empty_are_unknown():
    e=dict(id=0,obs=0,rec=1,price=1,liq=1000)
    o=m.outcome(e,[dict(id=1,obs=200,rec=201,price=3,liq=1000)],900)
    assert o['first_hit']=='UNKNOWN_GAP'
    assert m.outcome(e,[],900)['loss50'] is None
    assert m.stats([{'outcomes':{}}])['horizons']['900']['unknown']==1


def test_no_frame_at_signal_can_supply_outcome():
    e=dict(id=0,obs=0,rec=1,price=1,liq=1000)
    assert m.outcome(e,[dict(id=1,obs=1,rec=2,price=10,liq=1000)],900)['tail100'] is None
