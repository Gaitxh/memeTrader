from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from memetrader import relative_reawakening237 as r
from memetrader.strategy_revisions import revision_spec, revision_entry_signal

START = datetime(2026, 9, 19, tzinfo=timezone.utc)
TOKEN = 'solana:5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump'
POOL = '7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3'

def parent():
    from memetrader.forward_patterns import experiment_policies
    return revision_spec(next(p for p in experiment_policies() if p['arm_id']==r.PARENT))

def frame(seconds, **changes):
    at=START+timedelta(seconds=seconds)
    row=dict(id=seconds, token_id=TOKEN, pair_address=POOL, upstream_provider='dexscreener',
        observed_at=at.isoformat(), ingested_at=at.isoformat(), recorded_at=at.isoformat(),
        price=1., liquidity=5000., volume=400., buys=12, sells=8, pool_age_seconds=22000.)
    row.update(changes)
    return row

def history():
    return [frame(t) for t in (1,16,31,46,61,76,91,106,121,181)]+[
        frame(241,price=1.13,volume=1600.,buys=50,sells=20)]

def evaluate(rows, p=None, **kwargs):
    return r.signal(rows,p or r.policy(parent()),decision_at=kwargs.get('now',START+timedelta(seconds=241)),activated_at=kwargs.get('activation',START))

def test_relative_entry_does_not_require_absolute_silence():
    rows=history(); before=deepcopy(rows)
    old=parent()
    assert not revision_entry_signal(rows,old,decision_at=START+timedelta(seconds=241),activated_at=START)[0]
    ready,reason,evidence=evaluate(rows)
    assert ready and reason=='relative237_reawakening_ready'
    assert evidence['trade_growth']==3.5 and evidence['volume_growth']==4
    assert rows==before

def test_revised_policy_preserves_every_old_exit_and_never_mutates_parent():
    old=parent(); old.update(entry_paused=True,forward_started_at='old',behavior_contract_hash='old')
    before=deepcopy(old); new=r.policy(old)
    assert old==before and new['revision_of']==r.PARENT
    assert not new.get('entry_paused') and new.get('forward_started_at') is None
    for key in ('exit_family','exit_mode','hard_stop_return','trailing_activate_return','trailing_drawdown','max_hold_minutes','take_profit'):
        assert new.get(key)==old.get(key)
    assert new['entry_match_mode']=='isolated_pattern_observer'
    assert not new['live'] and new['no_historical_backfill']

@pytest.mark.parametrize('field,value', [('volume',None),('liquidity',None),('price',float('nan')),
    ('price',float('inf')),('buys',True),('sells',-1),('buys',2.5),('observed_at',None)])
def test_bad_critical_fields_are_not_zero_filled(field,value):
    rows=history(); rows[-1][field]=value
    assert not evaluate(rows)[0]

@pytest.mark.parametrize('field,value', [('volume',1100),('buys',15),('price',1.05),('liquidity',999),('pool_age_seconds',100)])
def test_relative_and_absolute_trade_conditions_are_both_required(field,value):
    rows=history(); rows[-1][field]=value
    assert not evaluate(rows)[0]

def test_future_late_duplicate_provider_and_pool_evidence_rejected():
    for field,value in [('recorded_at',(START+timedelta(seconds=242)).isoformat()),
                        ('upstream_provider','geckoterminal'),('pair_address','another-pool')]:
        rows=history(); rows[4][field]=value
        assert not evaluate(rows)[0]
    rows=history(); rows[4]['id']=rows[3]['id']
    assert not evaluate(rows)[0]
    rows=history(); rows[4],rows[5]=rows[5],rows[4]
    assert not evaluate(rows)[0]
    assert not evaluate(history(),activation=START+timedelta(seconds=130))[0]

def test_dense_intermediate_spike_is_not_hidden_by_sample_spacing():
    rows=history(); rows.insert(2,frame(20,price=1.3))
    assert evaluate(rows)[1]=='relative237_baseline_not_compressed'

def test_old_observations_cannot_manufacture_continuous_coverage():
    rows=history(); rows.pop(-2)
    assert evaluate(rows)[1]=='relative237_observation_gap'
    assert not evaluate(history()[-4:])[0]
    assert not evaluate(history(),now=START+timedelta(seconds=272))[0]

def test_zero_baseline_is_not_an_infinite_growth_signal():
    rows=history()
    for row in rows[:-1]: row.update(volume=0,buys=0,sells=0)
    assert evaluate(rows)[1]=='relative237_positive_baseline_required'

def test_irrelevant_missing_research_fields_do_not_veto_and_results_are_immutable():
    rows=history(); rows[-1].update(holders=None,signed_flow=None,buyers_5m=None)
    first=evaluate(rows); saved=deepcopy(first)
    assert first[0]
    rows.append(frame(250,price=1000))
    evaluate(rows,now=START+timedelta(seconds=250))
    assert first==saved
