"""Pinned unsigned Pump message/setup assembly. No wallet, key or send API."""
import base64
import hashlib
import json
import struct
from pathlib import Path
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.hash import Hash
from solders.rent import Rent
from solders.compute_budget import set_compute_unit_limit
from .models import iso,utcnow
from .pump_native import SOL,ZERO,native_cash_budget,pump_sol_exact_input_quote_v2,native_mint_controls

IDL=json.loads(Path(__file__).with_name('pump_native_idl.json').read_text(encoding='utf-8'))
PUMP='6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
ATA='ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL'
TOKEN='TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
RENT='SysvarRent111111111111111111111111111111111'
key=Pubkey.from_string


def global_fields(raw):
    offset=8
    def read(t):
        nonlocal offset
        if isinstance(t,dict):return [read(t['array'][0]) for _ in range(t['array'][1])]
        size={'bool':1,'u64':8,'pubkey':32}[t];part=raw[offset:offset+size];offset+=size
        if len(part)!=size:raise ValueError('incomplete_current_global')
        if t=='pubkey':return str(Pubkey.from_bytes(part))
        v=int.from_bytes(part,'little')
        if t=='bool' and v not in (0,1):raise ValueError('invalid_global_bool')
        return bool(v) if t=='bool' else v
    return {f['name']:read(f['type']) for f in IDL['global_fields']}


def addresses(frame,account_id):
    # A deterministic off-curve public identity: never a generated private key.
    payer=str(Pubkey.find_program_address([b'paper137',hashlib.sha256(account_id.encode()).digest()],key(PUMP))[0])
    g=frame['global_config'];mint=frame['base_mint'];program=frame['mint_state']['owner']
    found=dict(user=payer,base_mint=mint,quote_mint=SOL,base_token_program=program,
        quote_token_program=TOKEN,fee_recipient=g['fee_recipient'],buyback_fee_recipient=g['buyback_fee_recipients'][0])
    found['associated_base_user']=str(Pubkey.find_program_address([bytes(key(payer)),bytes(key(program)),bytes(key(mint))],key(ATA))[0])
    needed={a['name']:a for i in IDL['instructions'] for a in i['accounts']}
    def seed(s):
        if s['kind']=='const':return bytes(s['value'])
        return bytes(key(frame['curve_state']['creator'] if s['path']=='bonding_curve.creator' else found[s['path']]))
    for _ in range(len(needed)+1):
        for name,a in needed.items():
            if name in found:continue
            if 'address' in a:found[name]=a['address']
            elif 'pda' in a:
                try:
                    p=a['pda'];pg=Pubkey.from_bytes(seed(p['program'])) if p.get('program') else key(PUMP)
                    found[name]=str(Pubkey.find_program_address([seed(s) for s in p['seeds']],pg)[0])
                except KeyError:pass
    if set(needed)-set(found):raise ValueError('unresolved_native_message_accounts')
    return found


def messages(addrs,blockhash,spend,tokens):
    def ix(name,args):
        spec=next(i for i in IDL['instructions'] if i['name']==name)
        return Instruction(key(PUMP),bytes(spec['discriminator'])+b''.join(struct.pack('<Q',n) for n in args),
            [AccountMeta(key(addrs[a['name']]),a.get('signer',False),a.get('writable',False)) for a in spec['accounts']])
    create=Instruction(key(ATA),b'\x01',[AccountMeta(key(addrs['user']),True,True),
        AccountMeta(key(addrs['associated_base_user']),False,True),AccountMeta(key(addrs['user']),False,False),
        AccountMeta(key(addrs['base_mint']),False,False),AccountMeta(key(ZERO),False,False),
        AccountMeta(key(addrs['base_token_program']),False,False)])
    return {side:bytes(Message.new_with_blockhash([set_compute_unit_limit(1_400_000),*instructions],key(addrs['user']),Hash.from_string(blockhash)))
        for side,instructions in [('BUY',[create,ix('buy_exact_quote_in_v2',[spend,1])]),('SELL',[ix('sell_v2',[tokens,0])])]}


async def assemble(collector,frame,account_id,total_quote_raw):
    """Bounded cold-plan assembler: account batch, blockhash, four fee reads.

    Final resized messages are requoted; no assumed equivalence or extra retry.
    Caller must schedule only on rare candidates within its existing idle budget.
    """
    if native_mint_controls(frame)['status']!='CONTROLS_VERIFIED':raise ValueError('native_controls_not_verified')
    a=addresses(frame,account_id)
    if a['bonding_curve']!=frame['curve_address']:raise ValueError('native_curve_identity_mismatch')
    async def rpc(method,params):
        r=await collector.http.post(collector.rpc_url,json={'jsonrpc':'2.0','id':137,'method':method,'params':params})
        r.raise_for_status();body=r.json()
        if body.get('error') or body.get('result') is None:raise ValueError('native_cash_rpc_unavailable')
        return body['result']
    names=[RENT,a['associated_base_user'],a['user_volume_accumulator'],a['creator_vault'],a['bonding_curve']]
    result=await rpc('getMultipleAccounts',[names,{'encoding':'base64','commitment':'confirmed','minContextSlot':frame['slot']}])
    slot=result['context']['slot'];values=result['value'];account_at=iso()
    if slot<frame['slot'] or len(values)!=len(names) or values[1] is not None or values[2] is not None:
        raise ValueError('cold_setup_changed_or_incomplete')
    raw=lambda v:base64.b64decode(v['data'][0],validate=True)
    rent=Rent.from_bytes(raw(values[0]))
    for v in values[3:]:
        if v is None or v['owner']!=PUMP or v['lamports']<rent.minimum_balance(len(raw(v))):
            raise ValueError('native_existing_account_topup_unproven')
    # Require the curve used to plan economics to remain byte-identical.
    curve_hash=hashlib.sha256(values[4]['data'][0].encode()).hexdigest()
    if curve_hash!=frame['data_hash']:raise ValueError('native_curve_changed_during_cash_plan')
    if frame['mint_state']['owner']!= 'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb':
        raise ValueError('setup_size_only_proven_metadata_Token2022')
    setup=[dict(account_kind=n,present=False,required_data_bytes=size,rent_lock_lamports=rent.minimum_balance(size))
        for n,size in [('associated_base_user',170),('user_volume_accumulator',137)]]
    latest=await rpc('getLatestBlockhash',[{'commitment':'confirmed','minContextSlot':slot}])
    blockhash=latest['value']['blockhash']
    receipt=dict(token_id=frame['token_id'],curve=frame['curve_address'],account_id=account_id,
        account_context_slot=slot,account_recorded_at=account_at,setup=setup,addresses=a)
    probe=messages(a,blockhash,1,1)
    receipt['fees']=await collector.native_message_fee_receipts(probe,account_context_slot=slot)
    receipt['recorded_at']=iso()
    budget=native_cash_budget(total_quote_raw=total_quote_raw,receipt=receipt,now=utcnow(),
        token_id=frame['token_id'],curve=frame['curve_address'],account_id=account_id)
    quote=pump_sol_exact_input_quote_v2(quote_budget_raw=budget['spendable_quote_raw'],slippage_bps=400,
        bonding_curve=frame['curve_state'],global_config=frame['global_config'],fee_config=frame['fee_config'])
    final=messages(a,blockhash,budget['spendable_quote_raw'],quote['paper_token_amount_raw'])
    actual=await collector.native_message_fee_receipts(final,account_context_slot=slot)
    if any(actual[s]['fee_lamports']!=receipt['fees'][s]['fee_lamports'] for s in actual):
        raise ValueError('resized_message_fee_changed')
    receipt.update(fees=actual,recorded_at=iso(),message_hashes={s:hashlib.sha256(m).hexdigest() for s,m in final.items()},
        cash_budget=budget,buy_quote=quote,decision_eligible=False)
    return receipt
