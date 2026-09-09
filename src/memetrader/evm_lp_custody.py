"""GoPlus-reported V2 LP custody diagnostics; no trading authority or I/O."""
from decimal import Decimal, InvalidOperation
from .models import canonical_token_address, parse_time

BURN={'0x'+'0'*40,'0x'+'0'*36+'dead'}
TOL=Decimal('.0001')  # Reporting/rounding consistency, not a trading threshold.


def assess_lp(snapshot, source_at):
    out={'version':'evm-lp-custody109','state':'UNKNOWN','decision_eligible':False,
         'affects':'none','source':'goplus_evm','source_at':source_at,
         'coverage':'UNKNOWN','not_a_safety_guarantee':True}
    def unknown(reason,state='UNKNOWN'):
        return {**out,'state':state,'reason':reason}
    def number(value):
        if isinstance(value,bool) or value is None:raise ValueError('missing_number')
        n=Decimal(str(value))
        if not n.is_finite() or n<0:raise ValueError('invalid_number')
        return n
    if snapshot.chain not in {'bsc','robinhood','ethereum','eth','base'}:return unknown('not_evm')
    raw=snapshot.raw or {};g=raw.get('goplus_evm');pair=raw.get('pair') or {}
    pool=canonical_token_address(snapshot.chain,str(pair.get('pairAddress') or ''))
    out['pool']=pool
    if pair.get('chainId')!=snapshot.chain or canonical_token_address(snapshot.chain,str((pair.get('baseToken') or {}).get('address') or ''))!=canonical_token_address(snapshot.chain,snapshot.address):
        return unknown('token_surface_identity_unverified')
    if not isinstance(g,dict):return unknown('report_missing')
    dex=g.get('dex')
    # Top-level lp_holders cannot be attached to an arbitrary member of many pools.
    if not isinstance(dex,list) or len(dex)!=1:return unknown('lp_pool_binding_ambiguous')
    d=dex[0]
    if not isinstance(d,dict) or not pool or canonical_token_address(snapshot.chain,str(d.get('pair') or ''))!=pool:
        return unknown('exact_pool_not_matched')
    if d.get('liquidity_type')!='UniV2':return unknown('not_explicit_standard_v2')
    out['binding_basis']='single_reported_exact_UniV2_pool_not_onchain_attestation'
    holders=g.get('lp_holders')
    if not isinstance(holders,list) or not holders or len(holders)>32:return unknown('holders_missing_or_bounded')
    try:
        count=number(g.get('lp_holder_count'));supply=number(g.get('lp_total_supply'))
        if count!=count.to_integral_value() or count<=0 or supply<=0:return unknown('invalid_lp_supply_or_count')
        percentages=[];seen=set();locked=Decimal(0);burned=Decimal(0);top=Decimal(0);unknown_custody=Decimal(0)
        now=Decimal(str(parse_time(source_at).timestamp()))
        for h in holders:
            address=canonical_token_address(snapshot.chain,str(h.get('address') or ''))
            if not address or address in seen:raise ValueError('duplicate_or_missing_holder')
            seen.add(address);p=number(h.get('percent'));balance=number(h.get('balance'))
            if p>1 or abs(balance/supply-p)>TOL:raise ValueError('balance_percentage_mismatch')
            percentages.append(p)
            if address in BURN:burned+=p;continue
            if str(h.get('is_locked'))=='1':
                details=h.get('locked_detail')
                if not isinstance(details,list) or len(details)>32:unknown_custody+=p;continue
                amount=Decimal(0)
                for lock in details:
                    if number(lock.get('opt_time'))<=now<number(lock.get('end_time')):
                        amount+=number(lock.get('amount'))
                if amount>balance+supply*TOL:raise ValueError('locked_amount_exceeds_balance')
                locked+=min(p,amount/supply)
                unknown_custody+=max(Decimal(0),p-amount/supply)
            elif str(h.get('is_locked'))=='0' and str(h.get('is_contract'))=='0' and str(h.get('tag') or '').lower() in {'','deployer','creator','owner'}:
                top=max(top,p)
            else:unknown_custody+=p  # Contract/staking/tag is not an authenticated locker.
        total=sum(percentages)
        if count<len(holders) or total>1+TOL or (count<=len(holders) and abs(total-1)>TOL):
            raise ValueError('holder_count_percentage_coverage_mismatch')
        out.update(coverage='COMPLETE_RECONCILED' if count==len(holders) else 'PARTIAL_RECONCILED',
                   listed_fraction=float(total),lp_holder_count=int(count),listed_count=len(holders),
                   burned_fraction=float(burned),verified_report_lock_fraction=float(locked),
                   top_unlocked_non_custody_fraction=float(top),unknown_custody_fraction=float(unknown_custody),
                   majority_boundary=.5,high_custody_boundary=.9)
        state='LP_UNLOCKED_CONCENTRATED' if top>Decimal('.5') else 'LP_LOCKED_OR_BURNED_HIGH' if locked+burned>=Decimal('.9') else 'UNKNOWN'
        return {**out,'state':state,'reason':'reported_fraction_diagnostic_only'}
    except (ValueError,TypeError,KeyError,InvalidOperation,AttributeError) as exc:
        return unknown('lp_fields_missing' if str(exc)=='missing_number' else 'lp_fields_inconsistent',
                       'UNKNOWN' if str(exc)=='missing_number' else 'LP_COVERAGE_INCONSISTENT')
