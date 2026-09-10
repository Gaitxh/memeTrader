"""146 source/statistics/execution regressions; fixtures never touch production."""
import asyncio
from collections import deque
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from memetrader import mode_learning144 as old, mode_learning145 as learned
from memetrader.collectors import DexScreenerClient
from memetrader.models import TokenCandidate, iso, parse_time, utcnow
from memetrader.runtime import Runtime
from memetrader.store import Store
from memetrader.trajectory144 import ARMS, Engine
from test_l0_store import _snapshot
from test_strategy_delivery145 import _setup, _source_signal
from test_trajectory144 import row


def sample_group(s,mode,start,*,gains=20,floors=0,unknown=0):
    for i in range(gains+floors+unknown):
        at=start+timedelta(days=i%2,seconds=i)
        e=old.capture(s,episode_key=mode+':'+iso(at),token_id='bsc:'+format(i+1,'040x'),
            pair_address='0x'+'2'*40,chain='bsc',age_bucket='0_300',mode=mode,features={},
            decision_at=at,observed_at=at,ingested_at=at,recorded_at=at,signal=mode!='NO_SIGNAL')['episode']
        e['results']['5']={'status':'OBSERVED' if i<gains else 'MODEL_FLOOR_EVENT' if i<gains+floors else 'UNKNOWN',
            'costed_return':.05 if i<gains else None,'available_at':iso(at+timedelta(minutes=5))}


def state(at):return learned.initialize(now=at,contract={'feature':'trajectory144/v1','costs':{},'horizons':[5,15,30,60]})


def test_control_never_releases_or_occupies_tradable_slots_and_choose_uses_valid_mode():
    now=utcnow();s=state(now)
    for mode in ('NO_SIGNAL','unknown-mode'):sample_group(s,mode,now)
    assert not learned.train(s,cutoff_at=now+timedelta(days=2))['promoted']
    assert all(d['status']=='CONTROL_ONLY' for d in s['dispositions'].values())
    sample_group(s,ARMS[1],now)
    assert learned.train(s,cutoff_at=now+timedelta(days=2))['promoted']
    assert s['model']['selected_groups']==['bsc|0_300|'+ARMS[1]+'|5']
    at=now+timedelta(days=2,seconds=1)
    signals={arm:dict(decision_key=arm,observed_at=iso(at),recorded_at=iso(at),decision_evidence={}) for arm in (ARMS[1],ARMS[4])}
    assert old.choose(s,signals,{'chain':'bsc','pool_age_seconds':30},at,router_arm=learned.ROUTER)['decision_evidence']['learning_source_arm']==ARMS[1]
    disabled=state(now);disabled['available_modes']=[ARMS[4]]
    sample_group(disabled,ARMS[1],now)
    assert not learned.train(disabled,cutoff_at=now+timedelta(days=2))['promoted']


def test_known_floor_utility_is_minus_one_unknown_censored_and_old_seal_not_reused(tmp_path):
    now=utcnow();s=state(now);sample_group(s,ARMS[1],now,floors=5)
    assert not learned.train(s,cutoff_at=now+timedelta(days=2))['promoted']
    m=s['group_summaries']['bsc|0_300|'+ARMS[1]+'|5']
    assert m['endpoint_conditional_mean']==pytest.approx(.05)
    assert m['policy_model_mean']==pytest.approx(-.16)
    assert (m['endpoint_observed'],m['policy_model_n'],m['unknown'],m['floor_events'])==(20,25,0,5)
    assert m['sampled_equity_drawdown']==5
    other=state(now);sample_group(other,ARMS[1],now,unknown=5)
    assert learned.train(other,cutoff_at=now+timedelta(days=2))['promoted']
    assert other['group_summaries']['bsc|0_300|'+ARMS[1]+'|5']['policy_model_mean']==pytest.approx(.05)
    store=Store(tmp_path/'schema.sqlite3',initial_cash_usd=1000)
    prior={**deepcopy(other),'schema':'mode-learning145/v4'};prior['model']['version']='finite/v4:old'
    old_key='mode-learning145/v4:'+store.CHAIN_MEME_TRADER_ACTIVE_VERSION;store.set_kv(old_key,prior)
    persisted_prior=store.get_kv(old_key,None)
    c=learned.Coordinator(store)
    assert c.state['schema']=='mode-learning146/v5' and c.state['model']['releases']==0
    assert not c.state['groups'] and store.get_kv(old_key,None)==persisted_prior
    assert not learned.valid_model(prior['model'],c.state['contract_hash'])
    store.close()


@pytest.mark.parametrize('failure',['floor','missing','wrong_pool','wrong_token','future'])
def test_real_dex_missing_receipt_reaches_only_existing_exact_causal_learning(tmp_path,monkeypatch,failure):
    start=utcnow();clock=[start]
    for module in ('models','store','runtime','collectors'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'callbacks.sqlite3',initial_cash_usd=1000)
    c=learned.Coordinator(store);store._mode_learning144=c
    token=TokenCandidate('bsc','0x'+'1'*40,'Missing','MISS');pool='0x'+'2'*40
    c.capture_episode(episode_key='original',token_id=token.token_id,pair_address=pool,chain='bsc',
        age_bucket='0_300',mode=ARMS[1],features={},decision_at=start,observed_at=start,ingested_at=start,recorded_at=start)
    runtime=Runtime.__new__(Runtime);runtime.store=store;runtime.config={'paper':{'max_quote_age_seconds':45}}
    runtime._cohort_started_at=start;runtime._cohort_state={};runtime._cohort_saved_at=start
    idle=asyncio.Event();runtime._chain_meme_active_idle=lambda:idle
    store._trajectory144=Engine(start)
    monkeypatch.setattr('memetrader.cohort_experiments.consume_passive_cohort_batch',lambda frames,state,**kw:(state,{}))
    monkeypatch.setattr(store,'observe_chain_meme_pattern',lambda *a,**kw:pytest.fail('No entry projection during held priority'))
    async def deliver(second,*,bad=False,price=1.):
        received=start+timedelta(seconds=second);clock[0]=received
        pair={'chainId':'bsc','dexId':'pancakeswap','pairAddress':pool,'pairCreatedAt':int(start.timestamp()*1000),
            'baseToken':{'address':token.address,'name':token.name,'symbol':token.symbol},
            'quoteToken':{'address':'0x'+'3'*40,'symbol':'Q'},'priceUsd':price,
            'liquidity':{'usd':2000},'volume':{'m5':100},'txns':{'m5':{'buys':2,'sells':1}}}
        observed=received
        if bad:
            pair['priceUsd']=None;pair['liquidity']['usd']=10 if failure!='missing' else None
            if failure=='wrong_pool':pair['pairAddress']='0x'+'4'*40
            if failure=='wrong_token':pair['baseToken']['address']='0x'+'5'*40
            if failure=='future':observed+=timedelta(seconds=1)
        snap=DexScreenerClient._snapshot(pair,observed_at=observed)
        if bad:assert snap.raw['quote_usd_audit']['status']=='QUOTE_USD_UNKNOWN'
        runtime._cohort_batches=deque([(received,[(token,snap)])])
        await runtime.chain_meme_cohort_observer_once()
        if bad:
            assert runtime._paper_quote_rejections(token.token_id,token,snap,received)
            before=deepcopy(c.state['episodes']['original'])
            c.observe(token.token_id,snap,snap.ingested_at or received,received)
            assert c.state['episodes']['original']==before
    async def run():
        await deliver(1)
        assert c.state['episodes']['original']['entry']
        await deliver(31,bad=True)
        e=c.state['episodes']['original']
        if failure=='floor':assert e['first_floor']['liquidity_usd']==10
        else:assert e['first_floor'] is None
        if failure=='missing':
            old.expire(c.state,now=start+timedelta(minutes=7));c.classify_floor_labels()
            assert e['results']['5']['status']=='UNKNOWN'
        else:
            for second in range(61,302,30):await deliver(second,price=2.)
            assert e['results']['5']['status']==('MODEL_FLOOR_EVENT' if failure=='floor' else 'OBSERVED')
        # Missing data is not a floor; no receipt became a BUY or snapshot write.
        assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions').fetchone()[0]==0
        assert store.db.execute('SELECT COUNT(*) FROM token_snapshots').fetchone()[0]==0
    try:asyncio.run(run())
    finally:store.close()


def test_146_real_producer_safety_later_buy_frozen_mode_exit_and_parent_contract(tmp_path,monkeypatch):
    store,manager,gate,clock=_setup(tmp_path,monkeypatch)
    old_policy=dict(store.db.execute('SELECT * FROM chain_meme_trader_policy_additions WHERE arm_id=?',(ARMS[5],)).fetchone())
    added=store.db.execute('SELECT * FROM chain_meme_trader_policy_additions WHERE arm_id=?',(learned.ROUTER,)).fetchone()
    p=json.loads(added['policy_json']);assert p['notional_usd']==2
    assert p['entry_filter']['max_concurrent_positions']==2 and p['entry_filter']['include_pending_in_limit']
    assert manager.slots()==2  # Learned arm did not consume or clear the recipe slots.
    c=learned.Coordinator(store);store._mode_learning144=c
    token=TokenCandidate('bsc','0x'+'7'*40,'Learned','LRN');pool='0x'+'8'*40;store.upsert_token(token)
    clock[0]+=timedelta(seconds=1);engine=Engine(clock[0]);store._trajectory144=engine
    source,snapshot=_source_signal(ARMS[1],engine,token,pool,clock,clock[0])
    signals=c.signals(engine.pools[(token.token_id,pool)]['features'],{ARMS[1]:source},clock[0])
    sig=signals[learned.ROUTER]
    assert c.state['counts']['signal:'+learned.ROUTER]==1
    c.signals(engine.pools[(token.token_id,pool)]['features'],{ARMS[1]:source},clock[0])
    assert c.state['counts']['signal:'+learned.ROUTER]==1
    assert sig['decision_evidence']['learning_model']['version']==old.BASELINE
    stale=deepcopy(source);stale['observed_at']=iso(parse_time(added['activated_at'])-timedelta(seconds=1))
    assert learned.ROUTER not in c.signals(engine.pools[(token.token_id,pool)]['features'],{ARMS[1]:stale},clock[0])
    store.observe_chain_meme_pattern(token,snapshot,recorded_at=clock[0],cohort_signals=signals)
    clock[0]+=timedelta(seconds=10)
    item=row(clock[0],88,token=token.token_id,pool=pool,price=snapshot.price_usd*1.001,buys=888,volume=88888);engine.accept(item,clock[0])
    nxt=_snapshot(token,pool,clock[0],price=item['price_usd'])
    store.observe_chain_meme_pattern(token,nxt,recorded_at=clock[0],cohort_signals=signals)
    assert gate.pending and store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?',(learned.ROUTER,)).fetchone()[0]==0
    gate.cache[(token.token_id,pool)]={'status':'PASS','allow':True,'source_at':iso(clock[0]),'reasons':[]}
    clock[0]+=timedelta(seconds=2)
    with store._lock,store.db:gate.resume(token,_snapshot(token,pool,clock[0],price=item['price_usd']),clock[0])
    pos=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(learned.ROUTER,)).fetchone()
    assert pos and pos['stake_usd']==2 and pos['opened_at']>sig['recorded_at']
    assert c.state['actual_pending'][learned.ROUTER+':'+str(pos['shadow_cohort_id'])]['source_fill_id']==pos['source_entry_fill_id']
    assert store._cohort_router_exit_policy(p,pos)['max_hold_minutes']==5
    c.state['model'].update(version='fixture-future-release',selected_groups=['bsc|0_300|'+ARMS[4]+'|5'])
    assert store._cohort_router_exit_policy(p,pos)['max_hold_minutes']==5
    for second in (301,303):
        clock[0]=parse_time(pos['opened_at'])+timedelta(seconds=second)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,pool,clock[0],price=item['price_usd']),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])
    terminal=store.db.execute('SELECT status,close_reason FROM chain_meme_trader_positions WHERE arm_id=? AND shadow_cohort_id=?',(learned.ROUTER,pos['shadow_cohort_id'])).fetchone()
    assert terminal['status']=='closed' and 'max_hold' in terminal['close_reason']
    assert dict(store.db.execute('SELECT * FROM chain_meme_trader_policy_additions WHERE arm_id=?',(ARMS[5],)).fetchone())==old_policy
    c.resolve_actual(clock[0]);assert c.state['actual_groups'][learned.ROUTER][0]['source']=='actual_Paper_terminal_ledger'
    store.close()
