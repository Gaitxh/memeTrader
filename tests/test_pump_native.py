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


def fixed137():
    # Independent deployed-program simulation, slot445751903 (real Rent sysvar).
    return dict(status='verified',virtual_token_reserves_raw=810333883706620,
        virtual_quote_reserves_raw=39724366306,real_token_reserves_raw=530433883706620,
        real_quote_reserves_raw=9724366306,token_total_supply_raw=10**15,complete=False,
        is_mayhem_mode=False,is_cashback_coin=False,quote_mint='11111111111111111111111111111111',
        creator=SOL)


def fee137():
    return dict(status='verified',fee_tiers=[dict(market_cap_lamports_threshold=0,
        fees=dict(protocol_fee_bps=95,creator_fee_bps=30))])


def test_native_cash_budget_reserves_both_actual_fees_and_never_refunds_rent():
    from memetrader.pump_native import native_cash_budget
    now=utcnow()
    r=dict(token_id='t',curve='c',account_id='paper',recorded_at=iso(now),account_context_slot=10,
        setup=[dict(account_kind='associated_base_user',present=False,rent_lock_lamports=1887234),
               dict(account_kind='user_volume_accumulator',present=False,rent_lock_lamports=1678245)],
        fees={side:dict(fee_lamports=fee,context_slot=11,message_sha256='a'*64,recorded_at=iso(now))
              for side,fee in [('BUY',7000),('SELL',9000)]})
    def budget():return native_cash_budget(total_quote_raw=20_000_000,receipt=r,now=now,
        token_id='t',curve='c',account_id='paper')
    q=budget()
    assert q['spendable_quote_raw']==20_000_000-3565479-16000
    assert q['maximum_buy_debit_raw']+q['sell_network_fee_reserved_raw']==20_000_000
    assert q['rent_refund_raw']==0
    r['account_id']='different'
    with pytest.raises(ValueError,match='identity'):budget()
    r['account_id']='paper';r['fees']['SELL']['fee_lamports']=None
    with pytest.raises(ValueError,match='fee_invalid'):budget()


def test_native_fee_producer_uses_final_serialized_messages_without_send():
    import asyncio,json,httpx
    from solders.message import Message
    from solders.pubkey import Pubkey
    from solders.system_program import transfer,TransferParams
    from memetrader.collectors import SolanaHeldAccountCollector
    payer=Pubkey.new_unique();other=Pubkey.new_unique()
    messages={side:bytes(Message([transfer(TransferParams(from_pubkey=payer,to_pubkey=other,lamports=n))],payer))
              for side,n in [('BUY',1),('SELL',2)]}
    calls=[]
    async def run():
        def reply(req):
            body=json.loads(req.content);calls.append(body)
            assert body['method']=='getFeeForMessage'
            assert body['params'][1]['minContextSlot']==10
            return httpx.Response(200,json={'result':{'context':{'slot':11},'value':7000+len(calls)}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
            c=SolanaHeldAccountCollector.__new__(SolanaHeldAccountCollector);c.http=http;c.rpc_url='https://rpc.test'
            result=await c.native_message_fee_receipts(messages,account_context_slot=10)
            assert result['BUY']['fee_lamports']==7001 and result['SELL']['fee_lamports']==7002
            assert result['BUY']['message_sha256']!=result['SELL']['message_sha256']
    asyncio.run(run());assert len(calls)==2


@pytest.mark.parametrize('budget,net,tokens,recovery',[
    (10000000,9876542,201420619915,9753083),
    (30000000,29629629,603961714185,29259257),
    (100000000,98765431,2009710712819,97530861),
    (76222005257,75280992845,530433883702790,74339980432),
    (76222005258,75280992846,530433883705224,74339980433)])
def test_independent_deployed_v2_fixedstate(budget,net,tokens,recovery):
    from memetrader.pump_native import pump_sol_exact_input_quote_v2
    from memetrader.collectors import pump_bonding_curve_sell_quote_v1
    c=fixed137();original=deepcopy(c)
    q=pump_sol_exact_input_quote_v2(quote_budget_raw=budget,slippage_bps=0,
        bonding_curve=c,global_config=global_config(),fee_config=fee137())
    assert (q['curve_quote_in_raw'],q['token_amount_raw'])==(net,tokens)
    assert q['actual_quote_cost_raw']<=budget and c==original
    for key,delta in [('virtual_token_reserves_raw',-tokens),('real_token_reserves_raw',-tokens),
                      ('virtual_quote_reserves_raw',net),('real_quote_reserves_raw',net)]:c[key]+=delta
    sell=pump_bonding_curve_sell_quote_v1(token_amount_raw=tokens,slippage_bps=0,
        bonding_curve=c,global_config=global_config(),fee_config=fee137())
    assert sell['min_quote_raw']==recovery


@pytest.mark.parametrize('mode',['cap','cashback','mayhem','quote','fee'])
def test_exact_subset_rejects_unproved_state(mode):
    from memetrader.pump_native import pump_sol_exact_input_quote_v2
    c=fixed137();f=fee137();budget=10000000
    if mode=='cap':budget=76222005259  # Actual deployed error6021, not a refund.
    if mode=='cashback':c['is_cashback_coin']=True
    if mode=='mayhem':c['is_mayhem_mode']=True
    if mode=='quote':c['quote_mint']='USDC'
    if mode=='fee':f['fee_tiers'][0]['fees']['protocol_fee_bps']=96
    with pytest.raises(ValueError):
        pump_sol_exact_input_quote_v2(quote_budget_raw=budget,slippage_bps=400,
            bonding_curve=c,global_config=global_config(),fee_config=f)


def test_supported_subset_reaches_existing_unfunded_frame():
    now,frame,ref=sample();frame.update(curve_state=fixed137(),fee_config=fee137())
    e=native_economic_frame(frame,ref,now=now)
    assert e['status']=='OBSERVED_SHADOW' and e['decision_eligible'] is False
    assert 0<e['roundtrip_recovery_usd']<5
    assert e['transaction_fees']=='UNKNOWN_NETWORK_RENT_NOT_INCLUDED'
    assert e['safety_status']=='UNKNOWN_TOKEN_CONTROLS_NOT_ACQUIRED'


@pytest.mark.parametrize('case,expected',[('plain','CONTROLS_VERIFIED'),('missing','UNKNOWN'),
    ('slot','UNKNOWN'),('extension','UNKNOWN'),('authority','REJECT'),('supply','UNKNOWN')])
def test_same_slot_native_mint_control_boundary(case,expected):
    from memetrader.pump_native import native_mint_controls
    _,f,_=sample();f.update(mint_slot=f['slot'],mint_state=dict(status='verified',
        owner='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA',data_length=82,
        native_layout_verified=True,decimals=6,mint_authority=None,freeze_authority=None,initialized=True,supply_raw=10**15))
    if case=='missing':f.pop('mint_state')
    if case=='slot':f['mint_slot']-=1
    if case=='extension':f['mint_state']['native_layout_verified']=False
    if case=='authority':f['mint_state']['freeze_authority']=SOL
    if case=='supply':f['mint_state']['supply_raw']=1
    assert native_mint_controls(f)['status']==expected


@pytest.mark.parametrize('case',['metadata','duplicate','truncated','fee','hook','padding','coption','binding','length'])
def test_metadata_only_complete_tlv_through_actual_decoder(case):
    import base64
    from solders.pubkey import Pubkey
    from memetrader.collectors import SolanaHeldAccountCollector
    from memetrader.pump_native import native_mint_controls
    mint=Pubkey.from_string(SOL);raw=bytearray(166)
    raw[36:44]=(10**15).to_bytes(8,'little');raw[44]=6;raw[45]=1;raw[165]=1
    def tlv(k,v):return k.to_bytes(2,'little')+len(v).to_bytes(2,'little')+v
    metadata=bytes(32)+bytes(mint)+(80).to_bytes(4,'little')+b'n'*80+bytes(12)
    raw+=tlv(18,bytes(64))+tlv(19,metadata)
    assert len(raw)==398
    if case=='duplicate':raw+=tlv(18,bytes(64))
    if case=='truncated':raw=raw[:-1]
    if case=='fee':raw+=tlv(1,bytes(108))
    if case=='hook':raw+=tlv(14,bytes(64))
    if case=='padding':raw[82]=1
    if case=='coption':raw[0]=2
    if case=='binding':raw[270]=1
    if case=='length':raw[168]=63
    decoded=SolanaHeldAccountCollector.decode_account(
        dict(account_kind='token_mint',pubkey=SOL,native_metadata_controls=True),
        dict(owner='TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb',lamports=1,
             data=[base64.b64encode(raw).decode(),'base64']))
    _,frame,_=sample();frame.update(mint_state=decoded,mint_slot=frame['slot'])
    assert (native_mint_controls(frame)['status']=='CONTROLS_VERIFIED')==(case=='metadata')
    if case=='metadata':assert decoded['extension_types']==[18,19]

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
