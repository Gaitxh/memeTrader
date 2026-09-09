from copy import deepcopy
from datetime import timedelta
import pytest
from memetrader.evm_lp_custody import assess_lp
from memetrader.models import TokenCandidate,utcnow,iso
from memetrader.preentry_safety import assess
from test_paper_execution import _snapshot


def sample():
    t=TokenCandidate('bsc','0x'+'12'*20,'LP','LP');s=_snapshot(t,'0x'+'34'*20,utcnow())
    s.raw['goplus_evm']={'is_honeypot':'0','dex':[{'pair':'0x'+'34'*20,'liquidity_type':'UniV2'}],
        'lp_total_supply':'100','lp_holder_count':'1','lp_holders':[{'address':'0x'+'56'*20,'balance':'100','percent':'1','is_locked':'0','is_contract':'0','tag':''}]}
    return s


def test_majority_is_shadow_only_and_hard_veto_preserved():
    s=sample();a=assess(s,None,source_at=iso())
    assert a['allow'] and a['lp_custody_shadow']['state']=='LP_UNLOCKED_CONCENTRATED'
    assert not a['soft_hazard'] and not a['hard_veto']
    s.raw['goplus_evm']['is_honeypot']='1'
    assert assess(s,None,source_at=iso())['allow'] is False


@pytest.mark.parametrize('case',['sum','balance','duplicate','nan','missing'])
def test_inconsistent_never_custody_safe(case):
    s=sample();g=s.raw['goplus_evm'];h=g['lp_holders'][0]
    if case=='sum':h.update(balance='.001',percent='.00001',address='0x'+'0'*40)
    if case=='balance':h['balance']='.001'
    if case=='duplicate':g['lp_holders']*=2
    if case=='nan':h['percent']='NaN'
    if case=='missing':h.pop('percent')
    assert assess_lp(s,iso())['state']==('UNKNOWN' if case=='missing' else 'LP_COVERAGE_INCONSISTENT')


def test_pool_binding_v3_multi_curve_and_unknown_contract():
    s=sample();g=s.raw['goplus_evm']
    g['dex'][0]['liquidity_type']='UniV3';assert assess_lp(s,iso())['state']=='UNKNOWN'
    g['dex'][0]['liquidity_type']='UniV2';g['dex'].append(deepcopy(g['dex'][0]));assert assess_lp(s,iso())['state']=='UNKNOWN'
    g['dex']=g['dex'][:1];g['dex'][0]['pair']='0x'+'78'*20;assert assess_lp(s,iso())['state']=='UNKNOWN'
    g['dex'][0]['pair']='0x'+'34'*20;g['lp_holders'][0]['is_contract']='1';assert assess_lp(s,iso())['state']=='UNKNOWN'


def test_burn_and_expiring_lock_are_distinct_and_partial_coverage_visible():
    s=sample();g=s.raw['goplus_evm'];h=g['lp_holders'][0];now=utcnow()
    h['address']='0x'+'0'*36+'dead'
    assert assess_lp(s,iso(now))['state']=='LP_LOCKED_OR_BURNED_HIGH'
    h.update(address='0x'+'56'*20,is_locked='1',locked_detail=[{'amount':'100','opt_time':now.timestamp()-1,'end_time':now.timestamp()+1}])
    assert assess_lp(s,iso(now))['state']=='LP_LOCKED_OR_BURNED_HIGH'
    h['locked_detail'][0]['end_time']=now.timestamp()-1
    assert assess_lp(s,iso(now))['state']=='UNKNOWN'
    g['lp_holder_count']='20';h.update(is_locked='0',balance='60',percent='.6')
    a=assess_lp(s,iso(now));assert a['state']=='LP_UNLOCKED_CONCENTRATED' and a['coverage']=='PARTIAL_RECONCILED'


def test_lp_outcome_freezes_separate_category_and_later_original_pool_only():
    from memetrader.safety_veto_shadow import SafetyVetoShadow
    shadow=SafetyVetoShadow();s=sample();now=utcnow();lp=assess_lp(s,iso(now))
    item=dict(version='test',cohort_id=1,token_id=s.token_id,pool=lp['pool'],requested_at=iso(now),notional=5)
    anchor=dict(eligible=True,price_usd=s.price_usd,recorded_at=iso(now))
    a={'reasons':[lp['state']],'source_at':iso(now),'lp_custody':lp}
    shadow.capture(item,'LP_SHADOW',a,anchor,[],now);shadow.capture(item,'LP_SHADOW',a,anchor,[],now)
    assert shadow.state['triggers']==1
    later=now+timedelta(minutes=15);s.observed_at=later;s.price_usd*=2
    shadow.observe(s.token_id,s,later,later)
    row=next(iter(shadow.state['pending'].values()))
    assert row['category']=='LP_SHADOW' and row['lp_custody']==lp
    assert row['hard_veto']==[]
    assert row['results']['15']['status']=='OBSERVED_SHADOW'
    shadow.expire(now+timedelta(minutes=246))
    assert shadow.state['recent'][0]['results']['240']['status']=='UNKNOWN'
