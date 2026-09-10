from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
import pytest
from memetrader.models import utcnow,iso,TokenCandidate
from memetrader.market_microstructure import honeypot_pool_receipt
from memetrader.cohort_experiments import synthetic_harvest_policy
from memetrader.store import Store
from memetrader.preentry_safety import PreentrySafety
from test_l0_store import _snapshot

TOKEN='bsc:0x'+'12'*20
POOL='0x'+'34'*20

def report(now):
    return dict(honeypot_is=dict(simulationSuccess=True,honeypotResult={'isHoneypot':False},
        chain={'id':56},token={'address':TOKEN.split(':')[1]},
        pair={'chainId':56,'liquidity':2000,'pair':{'address':POOL,'type':'UniswapV2'}},
        simulationResult={'buyTax':0,'sellTax':0}),
        honeypot_is_observed_at=iso(now),honeypot_is_recorded_at=iso(now))

@pytest.mark.parametrize('mutation',['none','pool','chain','failed','honeypot','tax','fake_liquidity','no_clock','stale'])
def test_exact_pool_provider_proof(mutation):
    now=utcnow();raw=report(now);p=raw['honeypot_is']
    if mutation=='pool':p['pair']['pair']['address']='other'
    if mutation=='chain':p['chain']['id']=1
    if mutation=='failed':p['simulationSuccess']=False
    if mutation=='honeypot':p['honeypotResult']['isHoneypot']=True
    if mutation=='tax':p['simulationResult']['sellTax']=13
    if mutation=='fake_liquidity':p['simulationLiquidity']=True
    if mutation=='no_clock':raw.pop('honeypot_is_observed_at')
    if mutation=='stale':now+=timedelta(seconds=61)
    r=honeypot_pool_receipt(raw,token_id=TOKEN,pool=POOL,decision=now)
    assert bool(r)==(mutation=='none')
    if r:assert r['exact_size'] is False

@pytest.mark.parametrize('exit_kind',['time','distribution','hard_stop'])
def test_conditional_real_store_safety_later_fill_exit(tmp_path,monkeypatch,exit_kind):
    import memetrader.cohort_experiments as ce
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    policy=synthetic_harvest_policy();arm=policy['arm_id']
    assert policy['max_hold_minutes']==5 and policy['entry_filter']['max_concurrent_positions']==1
    # Test-only registration: production startup intentionally excludes this contract.
    monkeypatch.setattr(ce,'cohort_experiment_policies',lambda:[deepcopy(policy)])
    store=Store(tmp_path/'paper.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period();store.register_chain_meme_cohort_experiments()
    token=TokenCandidate('bsc',TOKEN.split(':')[1],'Test','T');store.upsert_token(token)
    gate=PreentrySafety(store,SimpleNamespace(config={}));store._preentry_safety=gate
    clock[0]+=timedelta(seconds=1)
    signal={arm:dict(episode_id='building',decision_key='building|'+arm,
        selected={'token_id':TOKEN,'pair_address':POOL},observed_at=iso(clock[0]),recorded_at=iso(clock[0]),
        decision_evidence={'signal_at':iso(clock[0]),'phase':'SYNTHETIC_LPI_BUILDING'})}
    for _ in range(2):
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0],cohort_signals=signal)
        clock[0]+=timedelta(seconds=1)
    assert len(gate.pending)==1
    proof=honeypot_pool_receipt(report(clock[0]),token_id=TOKEN,pool=POOL,decision=clock[0])
    gate.cache[(TOKEN,POOL)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[],exact_pool_sell_simulation=proof)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]==0
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    pos=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()
    assert pos and pos['stake_usd']==1
    store._microstructure119=SimpleNamespace(hazard_for=lambda *a:'synthetic_distribution' if exit_kind!='time' else None)
    clock[0]+=timedelta(seconds=301 if exit_kind=='time' else 2)
    for _ in range(2):
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0],price=.5 if exit_kind=='hard_stop' else 1),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(definition_version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION,now=clock[0],token_ids=[TOKEN])
        clock[0]+=timedelta(seconds=2)
    pos=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()
    assert pos['status']=='closed'
    store.close()


def test_provider_cache_time_and_failure_clear_old_proof():
    import asyncio
    from memetrader.strategy import SafetyChecker
    class Http:
        fail=False
        async def get(self,url,**kw):
            assert kw['params']['pair']==POOL and kw['ttl']==45
            if self.fail:raise RuntimeError('unavailable')
            return SimpleNamespace(json=lambda:report(at)['honeypot_is'],extensions={'observed_at':at})
    async def run():
        http=Http();checker=SafetyChecker(http,{'honeypot_is':True})
        token=TokenCandidate('bsc',TOKEN.split(':')[1],'Test','T')
        snap=_snapshot(token,POOL,utcnow())
        await checker._enrich_honeypot(snap)
        assert snap.raw['honeypot_is_observed_at']==iso(at)
        http.fail=True
        await checker._enrich_honeypot(snap)
        assert 'honeypot_is' not in snap.raw and 'honeypot_is_observed_at' not in snap.raw
    at=utcnow()-timedelta(seconds=20)
    asyncio.run(run())
