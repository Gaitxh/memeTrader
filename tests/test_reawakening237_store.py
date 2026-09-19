"""Real Store acceptance using an isolated database; never fabricates live orders."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
import pytest
from memetrader import relative_reawakening237 as r
from memetrader.forward_patterns import experiment_policies
from memetrader.strategy_revisions import revision_spec
from memetrader.store import Store
from memetrader.models import TokenCandidate, utcnow
from test_l0_store import _snapshot

TOKEN='5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump'
POOL='7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3'

def source(token, at, created, price=1., volume=400., buys=12, sells=8, depth=5000.):
    snap=_snapshot(token,POOL,at,price=price,liquidity=depth)
    raw=deepcopy(snap.raw)
    raw['pair']['pairCreatedAt']=round(created.timestamp()*1000)
    raw['pair']['volume']['m5']=volume
    raw['pair']['txns']['m5']={'buys':buys,'sells':sells}
    return replace(snap,volume_5m_usd=volume,buys_5m=buys,sells_5m=sells,raw=raw)

@pytest.fixture
def setup(tmp_path, monkeypatch):
    clock=[utcnow()]
    for name in ('store','models'):
        monkeypatch.setattr('memetrader.'+name+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'acceptance.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.activate_chain_paper_execution(dict(buy_slippage_pct=4,sell_slippage_pct=4,
        additional_fee_usd_each_fill=0,min_pool_liquidity_usd=1000),activated_at=clock[0])
    parent=revision_spec(next(p for p in experiment_policies() if p['arm_id']==r.PARENT))
    store.append_chain_meme_trader_policy(parent)
    version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    before=store._chain_meme_trader_registration(version)['definition_json']
    additions={a['arm_id']:a['policy_json'] for a in store.db.execute(
        'SELECT arm_id,policy_json FROM chain_meme_trader_policy_additions')}
    assert store.register_chain_meme_relative_reawakening237()==1
    assert store.register_chain_meme_relative_reawakening237()==0
    assert store._chain_meme_trader_registration(version)['definition_json']==before
    after={a['arm_id']:a['policy_json'] for a in store.db.execute(
        'SELECT arm_id,policy_json FROM chain_meme_trader_policy_additions')}
    assert all(after[k]==v for k,v in additions.items())
    token=TokenCandidate('solana',TOKEN,'Fixture','FIX')
    start=clock[0]; created=start-timedelta(hours=7)
    store.upsert_token(token,seen_at=start)
    try:
        yield store,clock,token,start,created
    finally:
        store.close()

def own(store):
    return store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',
                            (r.ARM,)).fetchone()

def enter(data):
    store,clock,token,start,created=data
    for seconds in (1,16,31,46,61,76,91,106,121,181):
        clock[0]=start+timedelta(seconds=seconds)
        store.observe_chain_meme_pattern(token,source(token,clock[0],created),recorded_at=clock[0])
        assert own(store) is None
    clock[0]=start+timedelta(seconds=241)
    trigger=source(token,clock[0],created,price=1.13,volume=1600,buys=50,sells=20)
    store.observe_chain_meme_pattern(token,trigger,recorded_at=clock[0])
    assert own(store) is None, 'Signal frame cannot buy'
    store.observe_chain_meme_pattern(token,trigger,recorded_at=clock[0])
    assert own(store) is None, 'Repeating cached signal cannot confirm'
    clock[0]=start+timedelta(seconds=245)
    store.observe_chain_meme_pattern(token,
        source(token,clock[0],created,price=1.14,volume=1700,buys=52,sells=21),recorded_at=clock[0])
    p=own(store)
    assert p is not None, [dict(row) for row in store.db.execute(
        'SELECT reason,feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1')]
    assert p['stake_usd']==20 and p['entry_execution_price_usd']==pytest.approx(1.14*1.04)
    assert p['paper_quantity_tokens']==pytest.approx(20/(1.14*1.04))
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?',
                            (r.PARENT,)).fetchone()[0]==0
    return p


def mark(data,price,depth=5000):
    store,clock,token,start,created=data
    clock[0]+=timedelta(seconds=2)
    snap=source(token,clock[0],created,price=price,depth=depth)
    store.upsert_chain_meme_trader_market_mark(token,snap,recorded_at=clock[0])
    store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[token.token_id])


def test_register_later_buy_and_frozen_evidence(setup):
    store,clock,token,start,created=setup
    p=enter(setup)
    assert p['opened_at']>start.isoformat().replace('+00:00','Z')
    fill=store.db.execute('SELECT * FROM chain_meme_trader_v6_entry_fills WHERE id=?',
                          (p['source_entry_fill_id'],)).fetchone()
    assert fill['token_id']==token.token_id and fill['entry_cohort_id']==p['shadow_cohort_id']
    assert fill['entry_market_price_usd']==pytest.approx(1.14)
    assert store._chain_meme_trader_effective_net_flows(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)[r.ARM]==pytest.approx(-20)


def test_partial_profits_require_next_marks_and_do_not_repeat(setup):
    store,clock,*_=setup
    initial=enter(setup); quantity=initial['paper_quantity_tokens']
    mark(setup,1.70)
    assert own(store)['pending_mark_id'] is not None
    assert own(store)['remaining_quantity_tokens']==quantity
    store.evaluate_chain_meme_trader_market_marks(now=clock[0])
    assert own(store)['remaining_quantity_tokens']==quantity
    mark(setup,1.71)
    p=own(store)
    assert p['remaining_quantity_tokens']==pytest.approx(quantity/2)
    assert p['realized_proceeds_usd']==pytest.approx(quantity/2*1.71*.96)
    assert p['next_tp_index']==1
    mark(setup,1.71)
    assert own(store)['remaining_quantity_tokens']==pytest.approx(quantity/2)
    mark(setup,2.9); mark(setup,2.91)
    p=own(store)
    proceeds=quantity/2*(1.71+2.91)*.96
    assert p['status']=='closed' and p['remaining_quantity_tokens']==0
    assert p['realized_pnl_usd']==pytest.approx(proceeds-20)
    flows=store.db.execute('SELECT SUM(net_cash_flow_usd) FROM chain_meme_trader_trades WHERE arm_id=?',(r.ARM,)).fetchone()[0]
    assert flows==pytest.approx(proceeds-20)
    store.record_chain_meme_trader_account_snapshots(definition_version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION,now=clock[0])
    account=store.db.execute('SELECT * FROM chain_meme_trader_account_snapshots WHERE arm_id=? ORDER BY id DESC LIMIT 1',(r.ARM,)).fetchone()
    assert account['cash_usd']==pytest.approx(980+proceeds)


def test_partial_then_fresh_dust_retains_sold_cash(setup):
    store,clock,*_=setup
    initial=enter(setup); quantity=initial['paper_quantity_tokens']
    mark(setup,1.70); mark(setup,1.71)
    proceeds=own(store)['realized_proceeds_usd']
    mark(setup,.01,depth=10)
    p=own(store)
    assert p['status']=='written_off' and p['remaining_quantity_tokens']==0
    assert p['realized_proceeds_usd']==pytest.approx(proceeds)
    assert p['realized_pnl_usd']==pytest.approx(proceeds-20)


def test_missing_depth_cannot_manufacture_exit_or_writeoff(setup):
    store,clock,*_=setup
    enter(setup); mark(setup,.6,depth=None)
    assert own(store)['status']=='open'
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side IN ('SELL','WRITEOFF')",(r.ARM,)).fetchone()[0]==0
