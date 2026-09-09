import pytest
from datetime import timedelta
from copy import deepcopy
from memetrader.models import utcnow,iso
from memetrader.pump_native import pump_bonding_curve_buy_quote_v1 as buy,native_economic_frame,absorption_probe,SOL


def curve():
    return dict(status='verified',virtual_token_reserves_raw=1_000_000_000_000,
        virtual_quote_reserves_raw=1_000_000_000,real_token_reserves_raw=800_000_000_000,
        real_quote_reserves_raw=500_000_000,token_total_supply_raw=1_000_000_000_000_000,
        complete=False,is_mayhem_mode=False,creator=SOL)

def global_config():return dict(status='verified',fee_basis_points=95,creator_fee_basis_points=30)

def test_frozen_sdk136_integer_example():
    q=buy(quote_budget_raw=100_000_000,slippage_bps=400,bonding_curve=curve(),global_config=global_config(),fee_config=None)
    assert q['token_amount_raw']==89_887_639_539
    assert q['curve_quote_in_raw']==98_765_431
    assert (q['protocol_fee_raw'],q['creator_fee_raw'])==(938272,296297)
    assert q['actual_quote_cost_raw']==100_000_000 and q['unspent_quote_raw']==0
    assert q['max_cost_slippage_raw']==104_000_000
    assert q['paper_token_amount_raw']==89_887_639_539*10000//10400

def test_supply_is_required_and_actual_supply_selects_tier():
    c=curve();c['token_total_supply_raw']=1000
    fee=dict(status='verified',fee_tiers=[dict(market_cap_lamports_threshold=0,fees=dict(protocol_fee_bps=10,creator_fee_bps=0)),
        dict(market_cap_lamports_threshold=10,fees=dict(protocol_fee_bps=100,creator_fee_bps=30))])
    q=buy(quote_budget_raw=100000,slippage_bps=0,bonding_curve=c,global_config=global_config(),fee_config=fee)
    assert q['fee_tier_index']==0 and q['market_cap_quote_raw']==1
    c['token_total_supply_raw']=None
    with pytest.raises(TypeError):buy(quote_budget_raw=100000,slippage_bps=0,bonding_curve=c,global_config=global_config(),fee_config=fee)

@pytest.mark.parametrize('budget',[2,3,10,100,1000,100000000])
def test_integer_affordability_capacity_and_roundtrip_no_free_money(budget):
    if budget==2:
        with pytest.raises(ValueError,match='budget_below_one_token'):
            buy(quote_budget_raw=budget,slippage_bps=0,bonding_curve=curve(),global_config=global_config(),fee_config=None)
        return
    q=buy(quote_budget_raw=budget,slippage_bps=0,bonding_curve=curve(),global_config=global_config(),fee_config=None)
    assert 0<q['token_amount_raw']<=curve()['real_token_reserves_raw']
    assert q['actual_quote_cost_raw']<=budget

def sample():
    now=utcnow();c=curve()
    frame=dict(identity_verified=True,quote_mint=SOL,slot=10,bundle_slot=10,curve_state=c,
        global_config=global_config(),fee_config={'status':'missing'},observed_at=iso(now),recorded_at=iso(now),
        curve_complete=False,**{k:c[k] for k in ['virtual_token_reserves_raw','virtual_quote_reserves_raw','real_token_reserves_raw','real_quote_reserves_raw']})
    ref=dict(input_amount_raw=10**9,output_amount_raw=100_000_000,minimum_output_amount_raw=96_000_000,completed_at=iso(now-timedelta(seconds=1)))
    return now,frame,ref

def test_postbuy_state_roundtrip_slippage_once_and_complete_handoff():
    now,frame,ref=sample()
    e=native_economic_frame(frame,ref,now=now)
    assert e['status']=='UNKNOWN' and e['diagnostic_status']=='LEGACY_ROUNDTRIP_COMPUTED'
    assert e['buy']['quote_budget_raw']==50_000_000
    assert 0<e['roundtrip_recovery_usd']<5 and e['decision_eligible'] is False
    no_slip=native_economic_frame(frame,ref,now=now,buy_slippage_bps=0,sell_slippage_bps=0)
    assert e['roundtrip_recovery_usd']<no_slip['roundtrip_recovery_usd']<5
    frame['curve_state']['real_token_reserves_raw']=100
    assert native_economic_frame(frame,ref,now=now)['status']=='SELL_UNAVAILABLE'

@pytest.mark.parametrize('change',['stale','future','slot','missing_output','unknown_fee','non_SOL','complete'])
def test_unknown_is_not_quote(change):
    now,frame,ref=sample()
    if change=='stale':ref['completed_at']=iso(now-timedelta(seconds=31))
    if change=='future':ref['completed_at']=iso(now+timedelta(seconds=1))
    if change=='slot':frame['bundle_slot']=9
    if change=='missing_output':ref.pop('output_amount_raw')
    if change=='unknown_fee':frame['fee_config']={'status':'unknown'}
    if change=='non_SOL':frame['quote_mint']='OTHER'
    if change=='complete':frame['curve_state']['complete']=True
    assert native_economic_frame(frame,ref,now=now)['status']=='UNKNOWN'

def test_two_frame_absorption_friction_and_strict_clocks():
    now,b,ref=sample();b['native_economics']=native_economic_frame(b,ref,now=now)
    # Synthetic verified economics fixture for the independent state-machine test.
    b['native_economics']['status']='OBSERVED_SHADOW'
    a=deepcopy(b);a.update(slot=9,observed_at=iso(now-timedelta(seconds=5)),recorded_at=iso(now-timedelta(seconds=4)))
    a['virtual_quote_reserves_raw']//=2;a['real_quote_reserves_raw']-=1;a['real_token_reserves_raw']+=1
    assert absorption_probe([a,b])['status']=='FRICTION_EXCEEDED'
    a['slot']=10
    assert absorption_probe([a,b])['status']=='UNKNOWN'

def test_absorption_needs_third_independent_requote_not_second_frame_fill():
    from memetrader.pump_native import advance_absorption
    now,frame,ref=sample();frame['native_economics']=native_economic_frame(frame,ref,now=now)
    frame['native_economics']['status']='OBSERVED_SHADOW'  # Synthetic state-machine fixture.
    trigger=advance_absorption(None,frame,{'status':'FRICTION_EXCEEDED'})
    assert trigger['status']=='TRIGGER_FROZEN'
    assert advance_absorption(trigger,frame,{'status':'FRICTION_EXCEEDED'})==trigger
    frame.update(slot=11,observed_at=iso(now+timedelta(seconds=5)),recorded_at=iso(now+timedelta(seconds=5)))
    result=advance_absorption(trigger,frame,{'status':'NOT_EXCEEDED'})
    assert result['status']=='REQUOTED_SHADOW' and result['decision_eligible'] is False
    frame['curve_complete']=True
    assert advance_absorption(trigger,frame,{})['status']=='MIGRATION_REQUIRED'


def test_unverified_v2_diagnostic_cannot_trigger_or_requote():
    from memetrader.pump_native import advance_absorption
    now,b,ref=sample();b['native_economics']=native_economic_frame(b,ref,now=now)
    assert b['native_economics']['quote_semantics']=='UNVERIFIED_V2_LEGACY_SDK_DIAGNOSTIC_ONLY'
    a=deepcopy(b);a.update(slot=9,observed_at=iso(now-timedelta(seconds=5)),recorded_at=iso(now-timedelta(seconds=4)))
    a['virtual_quote_reserves_raw']//=2;a['real_quote_reserves_raw']-=1;a['real_token_reserves_raw']+=1
    assert absorption_probe([a,b])['status']=='UNKNOWN'
    pending={'status':'TRIGGER_FROZEN','slot':9,'recorded_at':a['recorded_at']}
    assert advance_absorption(pending,b,{'status':'UNKNOWN'})==pending
