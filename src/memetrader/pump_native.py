"""Pump current-state integer buy and unfunded native economics. SDK 1.36.0."""
from copy import deepcopy
from .models import parse_time

ZERO='11111111111111111111111111111111'
SOL='So11111111111111111111111111111111111111112'
VERSION='pump-native-economic/105-v2-unverified'

def pump_bonding_curve_buy_quote_v1(*,quote_budget_raw,slippage_bps,bonding_curve,global_config,fee_config):
    c=bonding_curve;budget=int(quote_budget_raw);slip=int(slippage_bps)
    vt=int(c['virtual_token_reserves_raw']);vq=int(c['virtual_quote_reserves_raw'])
    rt=int(c['real_token_reserves_raw']);supply=int(c['token_total_supply_raw'])
    if budget<=1 or not 0<=slip<10000 or min(vt,vq,rt,supply)<=0 or rt>=vt:
        raise ValueError('invalid_current_curve_or_budget')
    if c.get('status')!='verified':raise ValueError('unverified_current_curve')
    if c.get('complete') is not False:raise ValueError('curve_complete_or_unknown')
    if global_config.get('status')!='verified' or (fee_config is not None and fee_config.get('status')!='verified'):
        raise ValueError('unverified_fee_bundle')
    cap=vq*supply//vt
    selected=global_config;index=None
    if fee_config is not None:
        tiers=fee_config['fee_tiers']
        if not tiers:raise ValueError('missing_fee_tiers')
        index=0
        for i in range(len(tiers)-1,-1,-1):
            if cap>=int(tiers[i]['market_cap_lamports_threshold']):index=i;break
        selected=tiers[index]['fees']
    protocol=int(selected['protocol_fee_bps'] if fee_config is not None else selected['fee_basis_points'])
    creator=int(selected['creator_fee_bps'] if fee_config is not None else selected['creator_fee_basis_points']) if c.get('creator')!=ZERO else 0
    if not c.get('creator') or min(protocol,creator)<0 or protocol+creator>=10000:raise ValueError('invalid_fees_or_creator')
    # Exact SDK budget sizing: never substitute newBondingCurve/global supply.
    net=(budget-1)*10000//(10000+protocol+creator)
    sdk_tokens=min(net*vt//(vq+net),rt)
    def cost(tokens):
        q=tokens*vq//(vt-tokens)+1
        return q,(q*protocol+9999)//10000,(q*creator+9999)//10000
    tokens=sdk_tokens
    if sum(cost(tokens))>budget:
        # Two separately rounded fees may exceed an integer exact-in budget.
        lo,hi=0,tokens
        while lo<hi:
            mid=(lo+hi+1)//2
            if sum(cost(mid))<=budget:lo=mid
            else:hi=mid-1
        tokens=lo
    if tokens<=0:raise ValueError('budget_below_one_token')
    q,pfee,cfee=cost(tokens);debit=q+pfee+cfee
    return {'calculation_version':'pump_bonding_curve_buy_quote_v1/sdk1.36.0','quote_budget_raw':budget,
        'sdk_token_amount_raw':sdk_tokens,'token_amount_raw':tokens,'curve_quote_in_raw':q,
        'protocol_fee_raw':pfee,'creator_fee_raw':cfee,'protocol_fee_bps':protocol,'creator_fee_bps':creator,
        'fee_tier_index':index,'market_cap_quote_raw':cap,'token_total_supply_raw':supply,
        'actual_quote_cost_raw':debit,'unspent_quote_raw':budget-debit,
        'max_cost_slippage_raw':(debit*(10000+slip)+9999)//10000,
        'paper_token_amount_raw':tokens*10000//(10000+slip),
        'reaches_complete':tokens==rt,'buy_slippage_bps':slip}

def native_economic_frame(frame,reference,*,now,buy_slippage_bps=400,sell_slippage_bps=400):
    from .collectors import pump_bonding_curve_sell_quote_v1
    out={'version':VERSION,'decision_eligible':False,'affects':'none','status':'UNKNOWN',
        'safety_status':'UNKNOWN_TOKEN_CONTROLS_NOT_ACQUIRED','notional_usd':5,
        'requested_instruction':'buy_exact_quote_in_v2',
        'quote_semantics':'UNVERIFIED_V2_LEGACY_SDK_DIAGNOSTIC_ONLY',
        'transaction_fees':'UNKNOWN_NETWORK_RENT_NOT_INCLUDED','observed_at':frame.get('observed_at'),
        'recorded_at':frame.get('recorded_at'),'slot':frame.get('slot')}
    try:
        if not frame.get('identity_verified') or frame.get('quote_mint') not in {ZERO,SOL}:
            raise ValueError('unverified_or_non_SOL_curve')
        if not reference:raise ValueError('missing_existing_WSOL_USDC_reference')
        observed=parse_time(frame['observed_at']);recorded=parse_time(frame['recorded_at']);ref_at=parse_time(reference['completed_at'])
        if not ref_at<=observed<=recorded<=now or not 0<=(observed-ref_at).total_seconds()<=30:
            raise ValueError('stale_future_or_incoherent_reference')
        if frame.get('bundle_slot')!=frame['slot'] or frame['slot']<=0:raise ValueError('incoherent_RPC_bundle')
        inp=int(reference['input_amount_raw']);usd=int(reference['output_amount_raw'])
        if inp<=0 or usd<=0:raise ValueError('missing_unhaircut_reference_output')
        budget=5_000_000*inp//usd
        curve=frame['curve_state'];global_config=frame['global_config'];fee_config=frame['fee_config']
        if fee_config.get('status') not in {'verified','missing'}:raise ValueError('fee_config_unknown')
        fee_config=fee_config if fee_config.get('status')=='verified' else None
        # SDK getFee uses the standard supply for non-mayhem sell. Do not silently
        # change the existing held sell semantics for a nonstandard deployment.
        if not curve.get('is_mayhem_mode') and curve['token_total_supply_raw']!=1_000_000_000_000_000:
            raise ValueError('nonstandard_nonmayhem_sell_fee_supply_unverified')
        buy=pump_bonding_curve_buy_quote_v1(quote_budget_raw=budget,slippage_bps=buy_slippage_bps,
            bonding_curve=curve,global_config=global_config,fee_config=fee_config)
        out.update(buy=buy,reference=deepcopy(reference),source_hashes=frame.get('bundle_hashes'),
            conversion_basis='existing_WSOL_USDC_output_reference_not_reverse_executable_USDC_buy')
        if buy['reaches_complete']:
            return {**out,'status':'SELL_UNAVAILABLE','reason':'hypothetical_buy_completes_curve_requires_PumpSwap_handoff'}
        post={**curve,'virtual_token_reserves_raw':curve['virtual_token_reserves_raw']-buy['token_amount_raw'],
            'virtual_quote_reserves_raw':curve['virtual_quote_reserves_raw']+buy['curve_quote_in_raw'],
            'real_token_reserves_raw':curve['real_token_reserves_raw']-buy['token_amount_raw'],
            'real_quote_reserves_raw':curve['real_quote_reserves_raw']+buy['curve_quote_in_raw']}
        sell=pump_bonding_curve_sell_quote_v1(token_amount_raw=buy['paper_token_amount_raw'],slippage_bps=sell_slippage_bps,
            bonding_curve=post,global_config=global_config,fee_config=fee_config)
        recovered=buy['unspent_quote_raw']+sell['min_quote_raw']
        # The current decoder/SDK port does not establish V2 exact-input fees
        # or reserve settlement. Never promote the legacy diagnostic to a frame.
        return {**out,'status':'UNKNOWN','diagnostic_status':'LEGACY_ROUNDTRIP_COMPUTED','sell':sell,'recovery_quote_raw':recovered,
            'roundtrip_recovery_ratio':recovered/budget,'roundtrip_recovery_usd':recovered*usd/inp/1_000_000,
            'friction_quote_raw':budget-recovered,'reason':'v2_exact_input_fee_and_state_semantics_not_verified',
            'cost_semantics':'Pump fees included once per leg; Paper buy quantity /1.04 and sell net *0.96 once; reference outAmount not minOutput; gas/rent excluded'}
    except (KeyError,TypeError,ValueError,ZeroDivisionError) as exc:
        return {**out,'reason':str(exc)}

def absorption_probe(frames):
    result={'hypothesis':'pump_native_absorption_v1','decision_eligible':False,'affects':'none','status':'UNKNOWN'}
    if len(frames)!=2:return {**result,'reason':'need_two_causal_frames'}
    a,b=frames
    try:
        if not (a['slot']<b['slot'] and parse_time(a['recorded_at'])<parse_time(b['observed_at'])
            and a['quote_mint']==b['quote_mint'] and a['curve_complete'] is False and b['curve_complete'] is False):
            raise ValueError('noncausal_or_complete_frames')
        e=b['native_economics']
        if e['status']!='OBSERVED_SHADOW':raise ValueError('missing_roundtrip_friction')
        grew=b['real_quote_reserves_raw']>a['real_quote_reserves_raw'] and b['real_token_reserves_raw']<a['real_token_reserves_raw']
        num=b['virtual_quote_reserves_raw']*a['virtual_token_reserves_raw']-a['virtual_quote_reserves_raw']*b['virtual_token_reserves_raw']
        den=a['virtual_quote_reserves_raw']*b['virtual_token_reserves_raw']
        if den<=0:raise ValueError('invalid_virtual_reserves')
        exceeds=grew and num*e['buy']['quote_budget_raw']>max(0,e['friction_quote_raw'])*den
        return {**result,'status':'FRICTION_EXCEEDED' if exceeds else 'NOT_EXCEEDED',
            'spot_displacement':num/den,'reserve_absorption':grew,
            'next_independent_curve_frame_required':True,'reason':'Shadow_only_safety_controls_and_native_settlement_not_registered'}
    except (KeyError,ValueError,TypeError) as exc:return {**result,'reason':str(exc)}

def advance_absorption(state,frame,probe):
    """Freeze a two-frame trigger; only a later coherent frame can re-quote it."""
    prior=state or {}
    if prior.get('status') in {'REQUOTED_SHADOW','MIGRATION_REQUIRED'}:return prior
    if frame.get('curve_complete') is True:
        return {'status':'MIGRATION_REQUIRED','decision_eligible':False,'affects':'none'}
    if prior.get('status')=='TRIGGER_FROZEN':
        if (frame['slot']>prior['slot'] and parse_time(frame['observed_at'])>parse_time(prior['recorded_at'])
            and frame['native_economics']['status']=='OBSERVED_SHADOW'):
            return {**prior,'status':'REQUOTED_SHADOW','requote_slot':frame['slot'],
                'requote_recorded_at':frame['recorded_at'],'reason':'WAIT_NATIVE_TOKEN_SAFETY_AND_SETTLEMENT','decision_eligible':False}
        return prior
    if probe['status']=='FRICTION_EXCEEDED':
        return {'status':'TRIGGER_FROZEN','slot':frame['slot'],'recorded_at':frame['recorded_at'],
            'decision_eligible':False,'affects':'none'}
    return {'status':'OBSERVING','decision_eligible':False,'affects':'none'}
