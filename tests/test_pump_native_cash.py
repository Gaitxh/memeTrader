import asyncio,base64,hashlib,json
import pytest
import httpx
from solders.rent import Rent
from solders.hash import Hash
from memetrader.models import utcnow,iso
from memetrader.collectors import SolanaHeldAccountCollector
from memetrader.pump_native_cash import assemble,addresses,PUMP,ZERO
from test_pump_native import fixed137,fee137,global_config,SOL


@pytest.mark.parametrize('vault_case',['system_empty','wrong_owner','nonempty','missing','underfunded'])
def test_cold_final_message_assembler_quotes_actual_resized_messages(vault_case):
    async def run():
        now=utcnow();g=global_config();g.update(fee_recipient=SOL,buyback_fee_recipients=[SOL])
        f=dict(token_id='solana:'+SOL,base_mint=SOL,slot=10,observed_at=iso(now),recorded_at=iso(now),
            curve_state=fixed137(),global_config=g,fee_config=fee137(),mint_slot=10,
            mint_state=dict(status='verified',native_layout_verified=True,decimals=6,
                owner='TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb',initialized=True,
                supply_raw=10**15,mint_authority=None,freeze_authority=None))
        f['curve_address']=addresses(f,'account')['bonding_curve']
        encoded=base64.b64encode(bytes(151)).decode();f['data_hash']=hashlib.sha256(encoded.encode()).hexdigest()
        account=dict(owner=PUMP,lamports=10**10,data=[encoded,'base64'])
        vault=dict(owner=ZERO,lamports=1308828,data=['','base64'])
        if vault_case=='wrong_owner':vault['owner']=PUMP
        if vault_case=='nonempty':vault['data']=[base64.b64encode(b'x').decode(),'base64']
        if vault_case=='missing':vault=None
        if vault_case=='underfunded':vault['lamports']=0
        rent=Rent(6333,1.0,50);calls=[];fees=[]
        def reply(req):
            b=json.loads(req.content);calls.append(b['method'])
            if b['method']=='getMultipleAccounts':
                result={'context':{'slot':11},'value':[{'data':[base64.b64encode(bytes(rent)).decode(),'base64']},None,None,vault,account]}
            elif b['method']=='getLatestBlockhash':result={'value':{'blockhash':str(Hash.default())}}
            else:
                assert b['method']=='getFeeForMessage';fees.append(b['params'][0])
                result={'context':{'slot':12},'value':5000}
            return httpx.Response(200,json={'result':result})
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
            c=SolanaHeldAccountCollector.__new__(SolanaHeldAccountCollector);c.http=http;c.rpc_url='https://rpc.test'
            if vault_case!='system_empty':
                with pytest.raises(ValueError,match='topup_unproven'):
                    await assemble(c,f,'account',20_000_000)
                assert calls==['getMultipleAccounts']
                return
            r=await assemble(c,f,'account',20_000_000)
        assert len(calls)==6 and len(fees)==4 and fees[:2]!=fees[2:]
        assert r['cash_budget']['spendable_quote_raw']==20_000_000-3565479-10000
        assert r['fees']['BUY']['message_sha256']==r['message_hashes']['BUY']
        assert not r['decision_eligible']
    asyncio.run(run())
