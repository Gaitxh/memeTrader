from datetime import timedelta
import pytest
from memetrader.models import iso, utcnow, parse_time
from memetrader.signal_clock234 import SignalClockCache


def test_same_clock_is_parsed_once_but_mutated_clock_reparsed():
    calls=[]
    def parser(v): calls.append(v); return parse_time(v)
    cache=SignalClockCache(parser); at=utcnow()
    signals=[{'recorded_at':iso(at)} for _ in range(40)]
    for _ in range(4):
        assert [cache(s) for s in signals]==[at]*40
    assert len(calls)==1 and cache.hits==159
    signals[0]['recorded_at']=iso(at+timedelta(seconds=1))
    assert cache(signals[0])==at+timedelta(seconds=1) and len(calls)==2


def test_fallback_and_errors_are_not_frozen():
    calls=[]
    def parser(v): calls.append(v); return len(calls)
    cache=SignalClockCache(parser)
    assert cache({'recorded_at':None})==1
    assert cache({'recorded_at':None})==2
    assert cache({'recorded_at':''})==3
    with pytest.raises(ValueError): SignalClockCache()({'recorded_at':'not-a-time'})


def test_cache_does_not_extend_any_original_deadline():
    at=utcnow(); signals=[{'recorded_at':iso(at-timedelta(seconds=i))} for i in (0,59,60,61,100)]
    cache=SignalClockCache()
    for sec in (0,1,20,60):
        now=at+timedelta(seconds=sec)
        expected=[s for s in signals if 0<=(now-parse_time(s['recorded_at'])).total_seconds()<=60]
        actual=[s for s in signals if 0<=(now-cache(s)).total_seconds()<=60]
        assert actual==expected
    another=SignalClockCache()
    assert another.values=={}
