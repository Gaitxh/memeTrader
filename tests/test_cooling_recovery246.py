from copy import deepcopy
from datetime import timedelta
import json
import pytest
from memetrader import cooling_recovery246 as m
from memetrader.failed_impulse_cooling import policy as old_policy, CORE
from memetrader.resource_bound_research import resource_policies, resource_entry_signal
from memetrader.models import TokenCandidate, iso, utcnow
from test_resource_bound_store import setup_store, quote


def parent():
    base = next(p for p in resource_policies() if p['arm_id']=='resource_cooling_hold_candidate_v1')
    value = old_policy(base)
    value['notional_usd'] = 20.
    value['entry_filter']['max_concurrent_positions'] = 8
    return value


def frame(at,price=1.,**changes):
    value = dict(id=1,token_id='solana:'+'A'*32,pair_address='B'*32,
        upstream_provider='dexscreener',observed_at=iso(at),ingested_at=iso(at),
        recorded_at=iso(at),price=price,liquidity=10000.,pool_age_seconds=7200.,
        buys=10.,sells=4.,volume=100.,volume_h1=2100.,buys_h1=100.,sells_h1=100.,
        price_change_m5=-2.,price_change_h1=30.)
    value.update(changes)
    return value


def path(at):
    return [frame(at),frame(at+timedelta(seconds=16),.97),frame(at+timedelta(seconds=32),1.)]

def evaluate(rows,at=None,start=None):
    return m.signal(rows,m.policy(parent()),decision_at=at or rows[-1]['recorded_at'],
        activated_at=start or iso(utcnow()-timedelta(hours=1)))


def test_recovery_is_not_a_copy_of_plain_cooling_and_needs_no_account_loss():
    at=utcnow(); rows=path(at)
    assert resource_entry_signal([rows[0]],parent(),decision_at=iso(at),
        activated_at=iso(at-timedelta(seconds=1)))[0]
    assert not evaluate(rows[:1])[0]
    assert not evaluate([rows[0],rows[1],frame(at+timedelta(seconds=32),.95)])[0]
    ok,reason,evidence=evaluate(rows)
    assert ok and reason=='cooling246_observed_recovery_ready'
    assert evidence['needs_parent_trade'] is False and evidence['frames']==3


def test_only_entry_contract_changes_parent_exits_and_parent_data_unchanged():
    p=parent(); old=deepcopy(p); new=m.policy(p)
    assert p==old and new['revision_of']==m.PARENT
    assert not new['entry_filter'].get('failed_impulse_cooling')
    for key in ('hard_stop_return','take_profit','max_hold_minutes','trailing_activate_return','trailing_drawdown','notional_usd'):
        assert new[key]==p[key]


@pytest.mark.parametrize('index,field,value',[(1,'price',None),(1,'liquidity',None),
    (1,'price',float('nan')),(1,'liquidity',8999),(1,'upstream_provider','geckoterminal'),
    (1,'pair_address','wrong'),(2,'sells',0),(2,'volume',None),(0,'volume_h1',None)])
def test_unknown_bad_depth_wrong_identity_or_no_activity_rejects(index,field,value):
    rows=path(utcnow()); rows[index][field]=value
    assert not evaluate(rows)[0]

def test_future_pre_activation_repeat_and_observation_gap_do_not_pass():
    at=utcnow(); rows=path(at)
    assert not evaluate(rows,at=at+timedelta(seconds=31))[0]
    assert not evaluate(rows,start=at+timedelta(seconds=1))[0]
    duplicate=[rows[0],deepcopy(rows[0]),*rows[1:]]
    assert not evaluate(duplicate)[0]
    gap=[rows[0],frame(at+timedelta(seconds=50),.97),frame(at+timedelta(seconds=70),1.)]
    assert not evaluate(gap)[0]


def test_dense_known_observations_keep_same_recovery_but_do_not_hide_bad_price():
    at=utcnow(); rows=path(at)
    dense=[rows[0],frame(at+timedelta(seconds=8),.99),rows[1],
        frame(at+timedelta(seconds=24),.98),rows[2]]
    assert evaluate(dense)[0]
    dense[3]['price']=1.10
    # Earlier local spike does not change the observed low/rebound contract.
    # It is not silently interpolated or removed from the recorded path.
    assert evaluate(dense)[2]['frames']==5


def test_actual_store_no_core_trade_next_frame_buy_and_real_stop_cash(tmp_path,monkeypatch):
    store,clock=setup_store(tmp_path,monkeypatch)
    try:
        store.register_chain_meme_resource_bound_research()
        store.register_failed_impulse_cooling103()
        version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        baseline=store._chain_meme_trader_registration(version)['definition_json']
        originals={r['arm_id']:r['policy_json'] for r in store.db.execute(
            'SELECT arm_id,policy_json FROM chain_meme_trader_policy_additions')}
        store.set_kv('chain-meme-account-loss-retirement/v1:'+version,
            dict(activated_at=iso(clock[0]),arms={CORE:dict(state='FAILED_FORWARD_EXPECTANCY')}))
        assert store.register_chain_meme_cooling_recovery246()==1
        assert store.register_chain_meme_cooling_recovery246()==0
        assert store._chain_meme_trader_registration(version)['definition_json']==baseline
        after={r['arm_id']:r['policy_json'] for r in store.db.execute(
            'SELECT arm_id,policy_json FROM chain_meme_trader_policy_additions')}
        assert all(after[a]==p for a,p in originals.items())
        token=TokenCandidate('solana','A'*32,'Recovery','REC')
        pool='B'*32; created=int((clock[0]-timedelta(hours=2)).timestamp()*1000)
        for price in (1.,.97,1.):
            clock[0]+=timedelta(seconds=16)
            store.observe_chain_meme_pattern(token,quote(token,pool,created,clock[0],price=price,cooling=True),recorded_at=clock[0])
            assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(m.ARM,)).fetchone()[0]==0
        clock[0]+=timedelta(seconds=16)
        store.observe_chain_meme_pattern(token,quote(token,pool,created,clock[0],price=1.001,cooling=True),recorded_at=clock[0])
        position=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(m.ARM,)).fetchone()
        assert position is not None and position['stake_usd']==20
        assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(CORE,)).fetchone()[0]==0
        assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(m.PARENT,)).fetchone()[0]==0
        assert position['entry_execution_price_usd']==pytest.approx(1.001*1.04)
        for index,price in enumerate((.74,.73)):
            clock[0]+=timedelta(seconds=2)
            store.upsert_chain_meme_trader_market_mark(token,
                quote(token,pool,created,clock[0],price=price),recorded_at=clock[0])
            store.evaluate_chain_meme_trader_market_marks(now=clock[0])
            if index==0:
                assert store.db.execute('SELECT status FROM chain_meme_trader_positions WHERE arm_id=?',(m.ARM,)).fetchone()[0]=='open'
        final=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(m.ARM,)).fetchone()
        assert final['status']=='closed' and final['remaining_quantity_tokens']==0
        expected=20/(1.001*1.04)*.73*.96-20
        assert final['realized_pnl_usd']==pytest.approx(expected)
        cash=store.db.execute('SELECT sum(net_cash_flow_usd) FROM chain_meme_trader_trades WHERE arm_id=?',(m.ARM,)).fetchone()[0]
        assert cash==pytest.approx(expected)
        assert final['closed_at']>position['opened_at']
        active=store._chain_meme_trader_effective_definition(version,baseline)
        assert next(p for p in active['policies'] if p['arm_id']==CORE)['entry_paused']
    finally:
        store.close()
