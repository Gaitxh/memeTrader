import asyncio
import base64
import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
import httpx
import pytest
from solders.hash import Hash
from solders.rent import Rent
from memetrader.models import utcnow, iso, TokenCandidate
from memetrader.store import Store
from memetrader.runtime import Runtime
from memetrader.collectors import SolanaHeldAccountCollector, pump_bonding_curve_sell_quote_v1
from memetrader.pump_native_cash import assemble, addresses, PUMP, ZERO
from memetrader.native_execution import ARM, register, buy, targets, account_assets, apply_curve_quote, dumps
from test_pump_native import fixed137, fee137, global_config, SOL


def setup(tmp_path,monkeypatch):
    clock=[utcnow()]
    monkeypatch.setattr('memetrader.store.utcnow',lambda:clock[0])
    monkeypatch.setattr('memetrader.models.utcnow',lambda:clock[0])
    store=Store(tmp_path/'native138.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period();register(store)
    from memetrader.preentry_safety import PreentrySafety
    from memetrader.rediscovery_funnel import CohortFlow
    monkeypatch.setattr('memetrader.rediscovery_funnel.utcnow',lambda:clock[0])
    store._preentry_safety=PreentrySafety(store,SimpleNamespace(config={}))
    store._cohort_flow=CohortFlow()
    token=TokenCandidate('solana',SOL,'native fixture','N');store.upsert_token(token)
    clock[0]+=timedelta(seconds=1);trigger_at=clock[0]
    clock[0]+=timedelta(seconds=1);now=clock[0]
    monkeypatch.setattr('memetrader.models.utcnow',lambda:clock[0])
    monkeypatch.setattr('memetrader.pump_native_cash.utcnow',lambda:clock[0])
    monkeypatch.setattr('memetrader.collectors.utcnow',lambda:clock[0])
    g=global_config();g.update(fee_recipient=SOL,buyback_fee_recipients=[SOL])
    f=dict(token_id=token.token_id,base_mint=SOL,slot=10,observed_at=iso(now),recorded_at=iso(now),
        curve_state=fixed137(),global_config=g,fee_config=fee137(),mint_slot=10,
        mint_state=dict(status='verified',native_layout_verified=True,decimals=6,
            owner='TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb',initialized=True,
            supply_raw=10**15,mint_authority=None,freeze_authority=None))
    f['curve_address']=addresses(f,'account')['bonding_curve']
    encoded=base64.b64encode(bytes(151)).decode();f['data_hash']=hashlib.sha256(encoded.encode()).hexdigest()
    calls=[]
    def reply(req):
        b=json.loads(req.content);calls.append(b['method'])
        if b['method']=='getMultipleAccounts':
            result={'context':{'slot':11},'value':[{'data':[base64.b64encode(bytes(Rent(6333,1.,50))).decode(),'base64']},None,None,
                dict(owner=ZERO,lamports=1308828,data=['','base64']),dict(owner=PUMP,lamports=10**10,data=[encoded,'base64'])]}
        elif b['method']=='getLatestBlockhash':result={'value':{'blockhash':str(Hash.default())}}
        else:
            assert b['method']=='getFeeForMessage'
            result={'context':{'slot':12},'value':5000}
        return httpx.Response(200,json={'result':result})
    async def plan():
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
            c=SolanaHeldAccountCollector.__new__(SolanaHeldAccountCollector);c.http=http;c.rpc_url='https://rpc.test'
            return await assemble(c,f,'account',50_000_000)
    p=asyncio.run(plan())
    p.update(execution_frame=f,execution_frame_sha256=hashlib.sha256(dumps(f).encode()).hexdigest(),
        reference=dict(completed_at=iso(now),input_amount_raw=1_000_000_000,output_amount_raw=100_000_000),
        trigger=dict(status='REQUOTED_SHADOW',slot=9,recorded_at=iso(trigger_at),requote_slot=10,requote_recorded_at=f['recorded_at'],
            token_id=f['token_id'],curve_address=f['curve_address'],probe={'status':'FRICTION_EXCEEDED'}))
    return store,clock,p


def test_real_plan_common_cash_runtime_held_sell_idempotence(tmp_path,monkeypatch):
    store,clock,p=setup(tmp_path,monkeypatch)
    before=store.db.execute('SELECT count(*) FROM chain_meme_trader_trades').fetchone()[0]
    assert buy(store,p,now=clock[0])=='BOUGHT'
    assert buy(store,p,now=clock[0])=='ALREADY_CONSUMED'
    assert store._cohort_flow.snapshot()['by_arm'][ARM]['BUY']==1
    assert store._cohort_flow.snapshot()['by_arm'][ARM]['SAFETY_AUTHORIZED']==1
    assert store.db.execute("SELECT count(*) FROM chain_meme_pattern_evidence WHERE source_key LIKE '%:BUY_AUTHORIZED_NATIVE_PROTOCOL'").fetchone()[0]==1
    pos=dict(store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone())
    assets=account_assets(store.db,store.CHAIN_MEME_TRADER_ACTIVE_VERSION,clock[0])
    debit=-store.db.execute("SELECT net_cash_flow_usd FROM chain_meme_trader_trades WHERE arm_id=? AND side='BUY'",(ARM,)).fetchone()[0]
    assert debit==pytest.approx(pos['stake_usd']+assets['rent'])
    assert debit+assets['reserve']<=5.000001 and assets['rent']>0
    other=deepcopy(p);other['trigger']['slot']=8
    assert buy(store,other,now=clock[0])=='MAX1'
    # The existing runtime held task supplies current raw-specific quotes/fees.
    runtime=Runtime.__new__(Runtime);runtime.store=store
    runtime._wsol_usdc_conversion=p['reference']
    async def ref(**kw):runtime._wsol_usdc_conversion=dict(p['reference'],completed_at=iso(clock[0]))
    runtime.chain_meme_wsol_reference_once=ref
    current_quote=[None];slot=[20]
    async def quotes(surfaces,**kw):
        c=deepcopy(fixed137());c['virtual_quote_reserves_raw']*=2;c['real_quote_reserves_raw']*=2
        q=pump_bonding_curve_sell_quote_v1(token_amount_raw=int(surfaces[0]['remaining_amount_raw']),slippage_bps=400,
            bonding_curve=c,global_config=global_config(),fee_config=fee137())
        current_quote[0]=dict(surfaces[0],pool_address=surfaces[0]['curve_address'],context_slot=slot[0],
            requested_at=iso(clock[0]),completed_at=iso(clock[0]),status='LOCAL_SURFACE_CURRENT',reason='',**q)
        return [current_quote[0]]
    async def fee(c,plan,q):return dict(context_slot=q['context_slot'],recorded_at=iso(clock[0]),fee_lamports=7000,
        token_amount_raw=int(q['remaining_amount_raw']),curve=q['pool_address'],account_id=plan['account_id'],message_sha256='a'*64)
    monkeypatch.setattr('memetrader.pump_native_cash.exit_fee',fee)
    monkeypatch.setattr('memetrader.native_execution.utcnow',lambda:clock[0])
    runtime.held_accounts=SimpleNamespace(bonding_curve_quotes=quotes)
    clock[0]+=timedelta(seconds=301)
    asyncio.run(runtime._native_held_once(targets(store)[0]))
    assert targets(store)[0]['state']['exit_intent']['reason']=='max_hold'
    # A trigger frame cannot settle itself, and the ordinary DEX engine cannot settle it.
    store.evaluate_chain_meme_trader_market_marks(now=clock[0])
    assert len(targets(store))==1
    clock[0]+=timedelta(seconds=2);slot[0]+=1
    target=targets(store)[0];asyncio.run(runtime._native_held_once(target))
    assert targets(store)==[]
    assert store._cohort_flow.snapshot()['by_arm'][ARM]['TERMINAL_SELL']==1
    closed=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()
    assert closed['status']=='closed' and closed['amount_raw']=='0'
    flows=store.db.execute('SELECT SUM(net_cash_flow_usd),SUM(realized_pnl_usd),count(*) FROM chain_meme_trader_trades WHERE arm_id=?',(ARM,)).fetchone()
    assets=account_assets(store.db,store.CHAIN_MEME_TRADER_ACTIVE_VERSION,clock[0])
    assert flows[0]+assets['rent']==pytest.approx(flows[1])
    assert assets['reserve']==0 and assets['rent']>0
    assert apply_curve_quote(store,target,current_quote[0],None,p['reference'],now=clock[0])=='TERMINAL'
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_trades').fetchone()[0]==before+2
    store.record_chain_meme_trader_account_snapshots(now=clock[0],definition_version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION)
    account=store.db.execute('SELECT * FROM chain_meme_trader_account_snapshots WHERE arm_id=? ORDER BY id DESC LIMIT 1',(ARM,)).fetchone()
    assert account['indicative_equity_usd']==pytest.approx(1000+flows[1])
    assert account['cash_usd']==pytest.approx(1000+flows[0])
    assert account['valuation_status']=='native_protocol_model_rent_at_cost'
    assert account['executable_equity_usd'] is None
    from memetrader.chain_web import ChainWebData
    from memetrader.runtime import initial_config
    cfg=initial_config();cfg['database']=str(store.path)
    config_path=tmp_path/'config.json';config_path.write_text(json.dumps(cfg),encoding='utf-8')
    monkeypatch.setattr('memetrader.chain_web.utcnow',lambda:clock[0])
    public=ChainWebData(config_path).state(compact=True,arm_id=ARM)
    public_account=next(s for s in public['strategies'] if s['arm_id']==ARM)
    assert public_account['account']['rent_locked_usd_at_cost']==pytest.approx(assets['rent'])
    store.close()
    reopened=Store(tmp_path/'native138.sqlite3',initial_cash_usd=1000)
    assert buy(reopened,p,now=clock[0])=='ALREADY_CONSUMED'
    assert reopened.db.execute('SELECT count(*) FROM chain_meme_trader_trades WHERE arm_id=?',(ARM,)).fetchone()[0]==2
    reopened.close()


@pytest.mark.parametrize('quote_case', ['capacity', 'stale', 'current'])
def test_native_web_uses_exit_surface_not_fresh_dex_mark(tmp_path, monkeypatch, quote_case):
    from memetrader.chain_web import ChainWebData
    from memetrader.runtime import initial_config
    from test_funding_epoch import _snapshot
    store, clock, plan = setup(tmp_path, monkeypatch)
    assert buy(store, plan, now=clock[0]) == 'BOUGHT'
    clock[0] += timedelta(seconds=1)
    monkeypatch.setattr('memetrader.chain_web.utcnow', lambda: clock[0])
    row = dict(store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?', (ARM,)).fetchone())
    token = TokenCandidate('solana', SOL, 'native fixture', 'N')
    snapshot = _snapshot(token, plan['curve'], clock[0])
    store.upsert_chain_meme_trader_market_mark(token, snapshot, recorded_at=clock[0])
    state = json.loads(store.db.execute('SELECT state_json FROM chain_meme_native_positions').fetchone()[0])
    state['mark'] = dict(value_usd=4., observed_at=iso(clock[0]), recorded_at=iso(clock[0]))
    with store.db:
        store.db.execute('UPDATE chain_meme_native_positions SET state_json=?', (dumps(state),))
        store.db.execute('UPDATE chain_meme_trader_positions SET allocated_cost_usd=1 WHERE arm_id=?', (ARM,))
    at = clock[0]-timedelta(seconds=20) if quote_case=='stale' else clock[0]
    store.set_kv('native-paper:last-held', dict(cohort_id=row['shadow_cohort_id'], token_id=token.token_id,
        remaining_amount_raw=row['amount_raw'], observed_at=iso(at), quote_recorded_at=iso(at), recorded_at=iso(at),
        quote_status='LOCAL_SURFACE_CURRENT' if quote_case=='current' else 'LOCAL_NO_DIRECT_CAPACITY',
        quote_reason='' if quote_case=='current' else 'native_capacity_budget_exhausted'))
    cfg=initial_config(); cfg['database']=str(store.path)
    path=tmp_path/'web.json'; path.write_text(json.dumps(cfg),encoding='utf-8')
    api=ChainWebData(path)
    ledger_before=[tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_trades')]
    expected = {'capacity':'native_exit_capacity_unavailable','stale':'native_quote_expired','current':None}[quote_case]
    for compact in (True, False):
        result=api.state(compact=compact,arm_id=ARM)
        account=next(s['account'] for s in result['strategies'] if s['arm_id']==ARM)
        assert account['valuation_unavailable_reasons']==({expected:1} if expected else {})
        strategy=next(s for s in result['strategies'] if s['arm_id']==ARM)
        views=[result['open_positions'][0], strategy['positions'][0]]
        for position in views:
            assert position['valuation_unavailable_reason']==expected
            assert position['indicative_source']=='native_protocol_model'
            assert position['indicative_price_usd'] is None
            assert position['indicative_mark_at']==iso(at)
            if expected:
                assert position['indicative_value_usd'] is None
                assert position['indicative_sellability']=='NATIVE_EXIT_UNAVAILABLE'
            else:
                assert position['indicative_value_usd']==4.
                assert position['indicative_unrealized_pnl_usd']==pytest.approx(4.-(row['stake_usd']-1.))
    token_view=api.token_detail(token.token_id)['positions'][0]
    assert token_view['valuation_unavailable_reason']==expected
    assert token_view['indicative_source']=='native_protocol_model'
    assert [tuple(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_trades')]==ledger_before
    store.close()


def test_bad_plan_and_completion_never_fabricate_exit(tmp_path,monkeypatch):
    store,clock,p=setup(tmp_path,monkeypatch)
    bad=deepcopy(p);bad['execution_frame']['mint_state']['freeze_authority']=SOL
    with pytest.raises(ValueError,match='hash'):buy(store,bad,now=clock[0])
    store._preentry_safety.cache[(p['token_id'],p['curve'])]={'status':'WAIT_HAZARD'}
    assert buy(store,p,now=clock[0])=='WAIT_SAFETY'
    store._preentry_safety.cache.clear()
    assert buy(store,p,now=clock[0])=='BOUGHT'
    target=targets(store)[0];clock[0]+=timedelta(seconds=2)
    q=dict(token_id=target['token_id'],pool_address=target['curve'],remaining_amount_raw=target['amount_raw'],
        context_slot=12,requested_at=iso(clock[0]),completed_at=iso(clock[0]),status='LOCAL_NO_DIRECT_CAPACITY',reason='bonding_curve_complete_migrated')
    with pytest.raises(ValueError,match='identity'):apply_curve_quote(store,target,dict(q,pool_address='wrong'),None,None,now=clock[0])
    assert apply_curve_quote(store,target,q,None,None,now=clock[0])=='MIGRATION_PENDING'
    assert targets(store)[0]['state']['mark'] is None
    assert store.db.execute("SELECT count(*) FROM chain_meme_trader_trades WHERE side!='BUY'").fetchone()[0]==0
    store.close()


def test_capacity_partial_runtime_cash_restart_and_later_close(tmp_path,monkeypatch):
    from memetrader.collectors import pump_curve_capacity_sell_quote
    from memetrader.native_execution import ensure_time_exit
    store,clock,p=setup(tmp_path,monkeypatch);assert buy(store,p,now=clock[0])=='BOUGHT'
    initial=targets(store)[0];initial_raw=int(initial['amount_raw'])
    clock[0]+=timedelta(seconds=301);ensure_time_exit(store,initial,now=clock[0])
    clock[0]+=timedelta(seconds=1);slot=[20];c=fixed137();c['real_quote_reserves_raw']=8_000_000
    r=Runtime.__new__(Runtime);r.store=store;r._wsol_usdc_conversion=p['reference']
    monkeypatch.setattr('memetrader.native_execution.utcnow',lambda:clock[0])
    async def ref(**kw):r._wsol_usdc_conversion=dict(p['reference'],completed_at=iso(clock[0]))
    r.chain_meme_wsol_reference_once=ref
    fee_amounts=[];fees_available=[False]
    async def quotes(surfaces,**kw):
        s=surfaces[0];assert s['native_capacity_exit']
        common=dict(s,pool_address=s['curve_address'],context_slot=slot[0],requested_at=iso(clock[0]),
            completed_at=iso(clock[0]),native_curve_state=deepcopy(c))
        try:
            q=pump_curve_capacity_sell_quote(token_amount_raw=int(s['remaining_amount_raw']),
                sold_quote_raw=s['native_sold_quote_raw'],sold_token_raw=s['native_sold_token_raw'],
                bonding_curve=c,global_config=global_config(),fee_config=fee137())
            return [dict(common,status='LOCAL_SURFACE_CURRENT',reason='',**q)]
        except ValueError as exc:return [dict(common,status='LOCAL_NO_DIRECT_CAPACITY',reason=str(exc))]
    async def fee(collector,plan,q):
        fee_amounts.append(q['quoted_amount_raw'])
        if not fees_available[0]:raise ValueError('current_fee_unavailable')
        return dict(context_slot=q['context_slot'],recorded_at=iso(clock[0]),fee_lamports=7000,
            token_amount_raw=q['quoted_amount_raw'],curve=q['pool_address'],account_id=plan['account_id'],message_sha256='b'*64)
    monkeypatch.setattr('memetrader.pump_native_cash.exit_fee',fee)
    r.held_accounts=SimpleNamespace(bonding_curve_quotes=quotes)
    asyncio.run(r._native_held_once(targets(store)[0]))
    assert int(targets(store)[0]['amount_raw'])==initial_raw  # No fee, no fill.
    fees_available[0]=True;clock[0]+=timedelta(seconds=2);slot[0]+=1
    asyncio.run(r._native_held_once(targets(store)[0]))
    partial=targets(store)[0];remaining=int(partial['amount_raw'])
    assert 0<remaining<initial_raw and fee_amounts[-1]==initial_raw-remaining
    assert partial['state']['mark'] is None and partial['state']['exit_intent']
    assert partial['state']['curve_gross_sold_raw']==8_000_000
    assert store._cohort_flow.snapshot()['by_arm'][ARM]['PARTIAL_SELL']==1
    row=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()
    assert row['allocated_cost_usd']==pytest.approx(row['stake_usd']*(initial_raw-remaining)/initial_raw)
    assert row['realized_pnl_usd']==pytest.approx(row['realized_proceeds_usd']-row['allocated_cost_usd'])
    assert len(account_assets(store.db,store.CHAIN_MEME_TRADER_ACTIVE_VERSION,clock[0])['values'])==1
    assert store.db.execute("SELECT count(*) FROM chain_meme_native_receipts WHERE kind LIKE 'PARTIAL_SELL:%'").fetchone()[0]==1
    store.close();store=Store(tmp_path/'native138.sqlite3',initial_cash_usd=1000);r.store=store
    # Independent newer slots do not replenish the same public reserve.
    for _ in range(2):
        clock[0]+=timedelta(seconds=2);slot[0]+=1
        asyncio.run(r._native_held_once(targets(store)[0]))
    assert int(targets(store)[0]['amount_raw'])==remaining and len(fee_amounts)==2
    # A real increase in later public reserves permits completion on that frame.
    c['real_quote_reserves_raw']=500_000_000;clock[0]+=timedelta(seconds=2);slot[0]+=1
    asyncio.run(r._native_held_once(targets(store)[0]))
    assert not targets(store)
    flows=store.db.execute('SELECT SUM(net_cash_flow_usd),SUM(realized_pnl_usd),COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=?',(ARM,)).fetchone()
    assets=account_assets(store.db,store.CHAIN_MEME_TRADER_ACTIVE_VERSION,clock[0])
    assert flows[2]==3 and flows[0]+assets['rent']==pytest.approx(flows[1])
    row=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(ARM,)).fetchone()
    assert row['realized_pnl_usd']==pytest.approx(flows[1]) and row['allocated_cost_usd']==pytest.approx(row['stake_usd'])
    store.close()


def test_native_task_failure_does_not_abort_existing_surface_lane(tmp_path,monkeypatch):
    store,clock,p=setup(tmp_path,monkeypatch);buy(store,p,now=clock[0])
    r=Runtime.__new__(Runtime);r.store=store
    async def fail(target):raise TimeoutError('bounded native RPC')
    r._native_held_once=fail
    asyncio.run(r.chain_meme_local_surface_once())
    assert len(targets(store))==1
    assert store.db.execute("SELECT count(*) FROM chain_meme_trader_trades WHERE side!='BUY'").fetchone()[0]==0
    store.close()


def test_production_paper_scheduler_runs_native_without_legacy_targets(tmp_path,monkeypatch):
    store,clock,p=setup(tmp_path,monkeypatch);buy(store,p,now=clock[0])
    clock[0]+=timedelta(seconds=301)
    monkeypatch.setattr('memetrader.native_execution.utcnow',lambda:clock[0])
    r=Runtime.__new__(Runtime);r.store=store;r.chain_meme_trader_only=True
    r.config={'bridge':{},'sources':{}};calls=[]
    async def run():
        r._stop=asyncio.Event()
        async def idle(*args,**kwargs):await r._stop.wait()
        async def quote(target):
            calls.append(('quote',target['cohort_id']))
            raise TimeoutError('no current quote')
        async def periodic(name,interval,action,**kwargs):
            if name=='native_paper_held':
                calls.append((name,interval));await action();r._stop.set()
            else:await r._stop.wait()
        r._periodic=periodic;r._native_held_once=quote
        for name in ('pump_loop','dex_discovery_stream_loop','seal_capital_research_once',
                     'seal_duration_research_once','chain_meme_v22_vault_shadow_loop'):
            setattr(r,name,idle)
        r.narrative_hold=SimpleNamespace(once=idle)
        await asyncio.wait_for(r.run_forever(),timeout=1)
    asyncio.run(run())
    assert ('native_paper_held',5) in calls and sum(c[0]=='quote' for c in calls)==1
    state=targets(store)[0]['state']
    assert state['exit_intent']['reason']=='max_hold' and state['mark'] is None
    assert store.db.execute("SELECT count(*) FROM chain_meme_trader_trades WHERE side!='BUY'").fetchone()[0]==0
    # Repeated unsuccessful attempts don't refresh the trigger clock.
    trigger=state['exit_intent'];clock[0]+=timedelta(seconds=10)
    from memetrader.native_execution import ensure_time_exit
    ensure_time_exit(store,targets(store)[0])
    assert targets(store)[0]['state']['exit_intent']==trigger
    store.close()


def test_migration_identity_then_strict_later_successor_exit(tmp_path,monkeypatch):
    from memetrader.native_execution import canonical_pool,confirm_successor
    from memetrader.collectors import PUMP_AMM_PROGRAM_ID
    store,clock,p=setup(tmp_path,monkeypatch);buy(store,p,now=clock[0])
    monkeypatch.setattr('memetrader.native_execution.utcnow',lambda:clock[0])
    target=targets(store)[0];clock[0]+=timedelta(seconds=2)
    q=dict(token_id=target['token_id'],pool_address=target['curve'],remaining_amount_raw=target['amount_raw'],
        context_slot=12,requested_at=iso(clock[0]),completed_at=iso(clock[0]),status='LOCAL_NO_DIRECT_CAPACITY',reason='bonding_curve_complete_migrated')
    apply_curve_quote(store,target,q,None,None,now=clock[0])
    assert confirm_successor(store,target,{'status':'UNKNOWN_RPC'},now=clock[0])=='MIGRATION_PENDING'
    pool,creator=canonical_pool(SOL);clock[0]+=timedelta(seconds=1)
    evidence=dict(status='RESOLVED',token_id=target['token_id'],pool_address=pool,base_mint=SOL,quote_mint=SOL,
        base_vault=SOL,quote_vault=PUMP,resolved_slot=13,resolved_at=iso(clock[0]),
        identity_facts=dict(pool=dict(status='verified',owner=PUMP_AMM_PROGRAM_ID,index=0,creator=creator,
            base_mint=SOL,quote_mint=SOL,base_vault=SOL,quote_vault=PUMP),
            base_vault=dict(status='verified',mint=SOL,authority=pool),quote_vault=dict(status='verified',mint=SOL,authority=pool)))
    wrong=deepcopy(evidence);wrong['identity_facts']['pool']['index']=1
    with pytest.raises(ValueError,match='canonical'):confirm_successor(store,target,wrong,now=clock[0])
    assert confirm_successor(store,target,evidence,now=clock[0])=='PUMPSWAP'
    target=targets(store)[0]
    q.update(pool_address=pool,context_slot=13,status='LOCAL_SURFACE_CURRENT',reason='',min_quote_raw=60_000_000,
        requested_at=iso(clock[0]),completed_at=iso(clock[0]))
    assert apply_curve_quote(store,target,q,None,None,now=clock[0])=='NO_NEW_STATE'
    clock[0]+=timedelta(seconds=1);q.update(context_slot=14,requested_at=iso(clock[0]),completed_at=iso(clock[0]))
    fee=dict(context_slot=14,recorded_at=iso(clock[0]),fee_lamports=7000,setup_rent_raw=12345,
        token_amount_raw=int(target['amount_raw']),curve=pool,account_id=p['account_id'],message_sha256='f'*64)
    ref=dict(p['reference'],completed_at=iso(clock[0]))
    assert apply_curve_quote(store,target,q,fee,ref,now=clock[0])=='SOLD'
    flows=store.db.execute('SELECT SUM(net_cash_flow_usd),SUM(realized_pnl_usd) FROM chain_meme_trader_trades WHERE arm_id=?',(ARM,)).fetchone()
    assets=account_assets(store.db,store.CHAIN_MEME_TRADER_ACTIVE_VERSION,clock[0])
    assert flows[0]+assets['rent']==pytest.approx(flows[1])
    assert store.db.execute("SELECT count(*) FROM chain_meme_native_receipts WHERE kind='CANONICAL_SUCCESSOR'").fetchone()[0]==1
    store.close()


@pytest.mark.parametrize('successor,partial',[(False,False),(True,False),(False,True)])
def test_current_unsigned_remaining_raw_fee_producers(tmp_path,monkeypatch,successor,partial):
    from solders.pubkey import Pubkey
    from solders.message import Message
    from memetrader.native_execution import canonical_pool
    from memetrader.pump_native_cash import exit_fee,successor_exit_fee,TOKEN
    from memetrader.collectors import PUMP_AMM_PROGRAM_ID
    store,clock,p=setup(tmp_path,monkeypatch);calls=[];clock[0]+=timedelta(seconds=1)
    pool,creator=canonical_pool(SOL)
    q=dict(pool_address=pool if successor else p['curve'],context_slot=20,remaining_amount_raw='123456789',
        native_global_config=p['execution_frame']['global_config'],native_curve_state=p['execution_frame']['curve_state'],
        quote_mint=SOL,base_mint=SOL,base_vault=SOL,quote_vault=PUMP,
        base_token_program=p['execution_frame']['mint_state']['owner'],
        native_swap_pool=dict(is_mayhem_mode=False,is_cashback_coin=False,coin_creator=SOL),
        native_swap_config=dict(protocol_fee_recipients=[SOL]))
    expected_amount=456789 if partial else 123456789
    if partial:q['quoted_amount_raw']=expected_amount
    def reply(req):
        b=json.loads(req.content);calls.append(b['method'])
        if b['method']=='getMultipleAccounts':
            authority=str(Pubkey.find_program_address([b'creator_vault',bytes(Pubkey.from_string(SOL))],Pubkey.from_string(PUMP_AMM_PROGRAM_ID))[0])
            def account(owner):
                raw=bytearray(165);raw[:32]=bytes(Pubkey.from_string(SOL));raw[32:64]=bytes(Pubkey.from_string(owner))
                return dict(owner=TOKEN,data=[base64.b64encode(raw).decode(),'base64'])
            result={'context':{'slot':21},'value':[{'data':[base64.b64encode(bytes(Rent(6333,1.,50))).decode(),'base64']},
                None,account(SOL),account(authority)]}
        elif b['method']=='getLatestBlockhash':result={'value':{'blockhash':str(Hash.default())}}
        else:
            assert b['method']=='getFeeForMessage'
            m=Message.from_bytes(base64.b64decode(b['params'][0]));instruction=m.instructions[-1]
            assert int.from_bytes(bytes(instruction.data)[8:16],'little')==expected_amount
            assert str(m.account_keys[instruction.program_id_index])==(PUMP_AMM_PROGRAM_ID if successor else PUMP)
            result={'context':{'slot':22},'value':6789}
        return httpx.Response(200,json={'result':result})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
            c=SolanaHeldAccountCollector.__new__(SolanaHeldAccountCollector);c.http=http;c.rpc_url='https://rpc.test'
            return await (successor_exit_fee(c,p,q) if successor else exit_fee(c,p,q))
    fee=asyncio.run(run())
    assert fee['fee_lamports']==6789 and fee['token_amount_raw']==expected_amount
    assert fee['curve']==q['pool_address'] and fee['account_id']==p['account_id']
    assert calls==(['getMultipleAccounts'] if successor else [])+['getLatestBlockhash','getFeeForMessage']
    if successor:assert fee['setup_rent_raw']==Rent(6333,1.,50).minimum_balance(165) and fee['rent_refund_raw']==0
    store.close()
