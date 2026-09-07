import json
from datetime import timedelta

import pytest

from memetrader.lifecycle_research import lifecycle_policies, evaluate_lifecycle_exit
from memetrader.models import TokenCandidate, utcnow
from test_resource_bound_store import setup_store, quote

TOKEN=TokenCandidate("solana","LifecycleFixture","Fixture")
PAIR="LifecyclePool"


def setup(tmp_path,monkeypatch):
    store,clock=setup_store(tmp_path,monkeypatch)
    version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original=store._chain_meme_trader_registration(version)["definition_json"]
    store.activate_chain_paper_execution({"buy_slippage_pct":4,"sell_slippage_pct":4,
        "additional_fee_usd_each_fill":.1,"min_pool_liquidity_usd":1000},activated_at=clock[0])
    assert store.register_chain_meme_lifecycle_research()==6
    assert store.register_chain_meme_lifecycle_research()==0
    created=int((clock[0]-timedelta(minutes=5)).timestamp()*1000)
    for i in range(2):
        clock[0]+=timedelta(seconds=16)
        store.observe_chain_meme_pattern(TOKEN,quote(TOKEN,PAIR,created,clock[0]),recorded_at=clock[0])
        rows=store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'lifecycle_%'").fetchall()
        assert len(rows)==(0 if i==0 else 6)
    assert len({p["source_entry_fill_id"] for p in rows})==1
    assert all(p["paper_quantity_tokens"]==pytest.approx(5/1.04) for p in rows)
    assert store._chain_meme_trader_registration(version)["definition_json"]==original
    return store,clock,created


def mark(store,clock,created,price,*,seconds=6,count=40):
    clock[0]+=timedelta(seconds=seconds)
    q=quote(TOKEN,PAIR,created,clock[0],price=price)
    q.buys_5m=q.sells_5m=count/2
    q.raw["pair"]["txns"]["m5"]={"buys":count/2,"sells":count/2}
    store.upsert_chain_meme_trader_market_mark(TOKEN,q,recorded_at=clock[0])
    store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[TOKEN.token_id])


def pos(store,kind):
    return store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?",("lifecycle_"+kind+"_v1",)).fetchone()


def evaluate(kind,sequence,*,mutate=None):
    p=next(x for x in lifecycle_policies() if x['arm_id']==f'lifecycle_{kind}_v1')['capital_exit_policy']
    start=utcnow();position={'token_id':TOKEN.token_id,'pair_address':PAIR,'opened_at':start.isoformat(),'stake_usd':5}
    state={};out=[]
    for i,(seconds,price) in enumerate(sequence):
        at=start+timedelta(seconds=seconds)
        f={'frame_id':str(i),'token_id':TOKEN.token_id,'pair_address':PAIR,'original_pool':True,
            'observed_at':at.isoformat(),'recorded_at':at.isoformat(),'provider':'dexscreener',
            'price_usd':price,'liquidity_usd':10000,'economic_value_usd':price*5,'buys':10,'sells':10}
        if mutate:mutate(i,f)
        result=evaluate_lifecycle_exit(position,f,state,now=at,policy=p)
        state=result[2];out.append(result)
    return out


@pytest.mark.parametrize('boundary',['missing','provider','gap','receipt'])
def test_giveback_area_never_crosses_bad_epoch(boundary):
    seq=[(10,2),(20,1.6),(30,1.6),(40,1.6),(50,1.6)]
    def mutation(i,f):
        if boundary=='missing' and i==2:f['original_pool']=False
        if boundary=='provider' and i>=2:f['provider']='geckoterminal'
        if boundary=='receipt' and i>=2:f['boundary_at']='new-boundary'
    if boundary=='gap':seq=[(10,2),(20,1.6),(60,1.6),(70,1.6)]
    out=evaluate('giveback_area',seq,mutate=mutation)
    assert all(x[0]!='SELL' for x in out)
    assert out[-1][2].get('area',0)==0


def test_giveback_integrates_only_after_loss_is_observed():
    out=evaluate('giveback_area',[(10,1.4),(12,1.6),(13,1.5),(15,1.5),(20,1.5)])
    assert out[2][2].get('area',0)==0
    assert out[3][2]['area']==pytest.approx(.2)
    assert out[4][2]['area']==pytest.approx(.7)
    assert all(x[0]!='SELL' for x in out)


@pytest.mark.parametrize('reclaim',[False,True])
def test_failed_rebound_requires_break_bounce_and_second_failure(reclaim):
    prices=[1.4,1.35,1.42,1.37,1.48,1.30,1.34 if not reclaim else 1.40,1.28]
    out=evaluate('failed_rebound',[(6*(i+1),p) for i,p in enumerate(prices)])
    assert all(x[0]!='SELL' for x in out[:-1])
    assert out[-1][0]==('HOLD' if reclaim else 'SELL')


@pytest.mark.parametrize('qualify',[True,False])
def test_renewal_is_one_fresh_decision_and_has_absolute_limit(qualify):
    prices=[1.4,1.30,1.45,1.36,1.5 if qualify else 1.40]
    out=evaluate('renewal',[(1776+6*i,p) for i,p in enumerate(prices)]+[(1806,1.55),(7200,1.55)])
    assert out[4][2]['extension_granted'] is qualify
    assert out[4][0]==('HOLD' if qualify else 'SELL')
    assert out[-1][0]=='SELL'


def test_risk_trim_partial_fill_uses_receipt_and_does_not_repeat(tmp_path,monkeypatch):
    store,clock,created=setup(tmp_path,monkeypatch)
    for i in range(20):
        mark(store,clock,created,1.02-.002*i,count=100-2*i)
    before=pos(store,'risk_trim')
    assert before['pending_mark_id'] is not None and before['allocated_cost_usd']==0
    mark(store,clock,created,.98,count=58)
    after=pos(store,'risk_trim')
    assert after['status']=='open'
    assert after['remaining_quantity_tokens']==pytest.approx((5/1.04)*.25,abs=1e-7)
    assert after['realized_proceeds_usd']==pytest.approx((5/1.04)*.75*.98*.96-.1,abs=1e-6)
    assert after['allocated_cost_usd']==pytest.approx(5.1*.75,abs=1e-6)
    mark(store,clock,created,.981,count=56)
    assert pos(store,'risk_trim')['pending_mark_id'] is None
    assert pos(store,'baseline')['remaining_quantity_tokens']==pytest.approx(5/1.04)
    store.close()


def test_renewal_store_extends_only_qualified_arm_and_exits_at_limit(tmp_path,monkeypatch):
    store,clock,created=setup(tmp_path,monkeypatch)
    mark(store,clock,created,1.4,seconds=1776)
    for price in (1.30,1.45,1.36,1.5):mark(store,clock,created,price)
    assert pos(store,'baseline')['pending_mark_id'] is not None
    assert pos(store,'renewal')['pending_mark_id'] is None
    mark(store,clock,created,1.51)
    assert pos(store,'baseline')['status']=='closed'
    assert pos(store,'renewal')['status']=='open'
    mark(store,clock,created,1.52,seconds=5394)
    assert pos(store,'renewal')['pending_mark_id'] is not None
    mark(store,clock,created,1.53)
    assert pos(store,'renewal')['status']=='closed'
    store.close()


@pytest.mark.parametrize('interruption',[None,'provider','missing','late'])
def test_shadow_addition_next_quote_budget_and_formal_ledger_isolation(tmp_path,monkeypatch,interruption):
    store,clock,created=setup(tmp_path,monkeypatch)
    for price in (1.3,1.24,1.29,1.36):mark(store,clock,created,price)
    before=pos(store,'probe');state=json.loads(before['capital_exit_state_json'])['staged_probe']
    assert state['status']=='QUALIFIED' and 'shadow_fill' not in state
    if interruption=='missing':
        clock[0]+=timedelta(seconds=1)
        store.record_chain_meme_trader_pool_mark_miss(token_id=TOKEN.token_id,pair_address=PAIR,
            chain=TOKEN.chain,address=TOKEN.address,recorded_at=clock[0])
    if interruption=='provider':
        clock[0]+=timedelta(seconds=6)
        q=quote(TOKEN,PAIR,created,clock[0],price=1.38);q.provider='geckoterminal'
        store.upsert_chain_meme_trader_market_mark(TOKEN,q,recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[TOKEN.token_id])
    else:mark(store,clock,created,1.38,seconds=31 if interruption=='late' else 6)
    after=pos(store,'probe');state=json.loads(after['capital_exit_state_json'])['staged_probe']
    assert after['stake_usd']==before['stake_usd']
    assert after['remaining_quantity_tokens']==before['remaining_quantity_tokens']
    if interruption:
        assert state['status']=='COMPLETE_NO_SHADOW' and 'shadow_fill' not in state
    else:
        assert state['status']=='SHADOW_OPEN'
        assert state['shadow_fill']['quantity_tokens']==pytest.approx(5/1.38/1.04)
        assert state['shadow_fill']['total_cost_usd']==pytest.approx(5.1)
        assert state['shadow_account']['cash_after_fill_usd']==pytest.approx(994.9)
        mark(store,clock,created,1.37,seconds=1800)
        mark(store,clock,created,1.36)
        closed=pos(store,'probe');state=json.loads(closed['capital_exit_state_json'])['staged_probe']
        assert closed['status']=='closed' and state['status']=='SHADOW_CLOSED'
        assert state['shadow_exit']['shadow_net_recovery_usd']==pytest.approx((5/1.38/1.04)*1.36*.96-.1)
        assert closed['realized_pnl_usd']==pytest.approx((5/1.04)*1.36*.96-.1-5.1)
    store.close()
