from copy import deepcopy
from datetime import timedelta
import pytest
from memetrader.models import iso, utcnow, TokenCandidate
from memetrader.pressure_sequence234 import Tracker, YOUNG, MATURE, HYBRID, ARMS, PARENT, policies, hybrid_signal
from test_old_pool_absorption227 import TOKEN, POOL


def frame(at, **changes):
    row=dict(chain='solana',token_id=TOKEN,pair_address=POOL,provider='dexscreener',
        observed_at=iso(at),ingested_at=iso(at),recorded_at=iso(at),
        price_usd=1.,liquidity_usd=6000.,volume_5m_usd=500.,buys_5m=5,sells_5m=4,pool_age_seconds=120)
    row.update(changes)
    return row


def sequence(at, *, chain='solana', age=120):
    identity={} if chain=='solana' else dict(chain=chain,token_id=chain+':0x'+'ab'*20,pair_address='0x'+'cd'*20)
    rows=[frame(at,**identity,pool_age_seconds=age),
          frame(at+timedelta(seconds=10),**identity,pool_age_seconds=age+10,price_usd=1.02,buys_5m=9,volume_5m_usd=650),
          frame(at+timedelta(seconds=16),**identity,pool_age_seconds=age+16,price_usd=1.06,buys_5m=10,sells_5m=5,volume_5m_usd=700)]
    return rows


def run_sequence(rows):
    tracker=Tracker(utcnow()-timedelta(seconds=1))
    out=[]
    for row in rows:
        out.append(tracker.accept(row,row['recorded_at'],floor=1000))
    return tracker,out


def test_young_entry_is_independent_and_freezes_three_ordered_observations():
    at=utcnow(); rows=sequence(at); tracker,out=run_sequence(rows)
    assert out[:2]==[{},{}] and set(out[-1])=={YOUNG}
    signal=out[-1][YOUNG]; frozen=deepcopy(signal)
    assert signal['decision_evidence']['first']['observed_at']==iso(at)
    assert signal['decision_evidence']['pressure']['price_usd']==1.02
    assert signal['decision_evidence']['confirmation']['price_usd']==1.06
    assert tracker.accept(frame(at+timedelta(seconds=25),price_usd=100),at+timedelta(seconds=25),floor=1000)=={}
    assert signal==frozen

@pytest.mark.parametrize('chain',['solana','bsc','robinhood'])
def test_mature_entry_uses_own_lifecycle_not_young_parent(chain):
    _,out=run_sequence(sequence(utcnow(),chain=chain,age=22000))
    assert set(out[-1])=={MATURE}

@pytest.mark.parametrize('changes',[{'price_usd':None},{'volume_5m_usd':None},
    {'liquidity_usd':1999},{'buys_5m':None},{'sells_5m':None},
    {'price_usd':float('inf')},{'volume_5m_usd':True},{'chain':'unverified'},
    {'provider':'other'},{'ingested_at':None}])
def test_unknown_critical_inputs_do_not_seed_or_become_zero(changes):
    at=utcnow(); t=Tracker(at-timedelta(seconds=1))
    assert t.accept(frame(at,**changes),at,floor=1000)=={}
    assert not t.states


def test_frame_before_activation_and_future_receipt_are_not_accepted():
    at=utcnow(); t=Tracker(at+timedelta(seconds=1))
    assert t.accept(frame(at),at,floor=1000)=={}
    assert not t.states
    t=Tracker(at-timedelta(seconds=1))
    assert t.accept(frame(at,recorded_at=iso(at+timedelta(seconds=1))),at,floor=1000)=={}
    assert not t.states


def test_dense_updates_do_not_reset_stage_clock():
    at=utcnow(); a,b,c=sequence(at)
    dense=[a,frame(at+timedelta(seconds=5)),b,
           frame(at+timedelta(seconds=12),price_usd=1.02,buys_5m=9,volume_5m_usd=650),c]
    _,out=run_sequence(dense)
    assert set(out[-1])=={YOUNG}

@pytest.mark.parametrize('change',[{'provider':'geckoterminal'},
    {'observed_at':None},{'price_usd':.8},{'liquidity_usd':1000},
    {'price_usd':1.30},{'pair_address':'0x'+'ef'*20}])
def test_broken_stage_cannot_finish_old_opportunity(change):
    at=utcnow(); a,b,c=sequence(at); b.update(change)
    _,out=run_sequence([a,b,c])
    assert out[-1]=={}


def test_costly_price_chase_is_not_renamed_as_activity_before_price():
    at=utcnow(); a,b,c=sequence(at); b['price_usd']=1.1
    _,out=run_sequence([a,b,c])
    assert all(not x for x in out)


def test_expiry_gap_and_duplicate_remain_nontrading():
    at=utcnow(); a,b,c=sequence(at); t=Tracker(at-timedelta(seconds=1))
    assert t.accept(a,at,floor=1000)=={}
    assert t.accept(a,at,floor=1000)=={}
    late=at+timedelta(seconds=50)
    assert t.accept(frame(late,price_usd=1.02,buys_5m=9,volume_5m_usd=650),late,floor=1000)=={}
    assert t.counts['episode_boundary_reset']==1
    assert t.accept(c,at+timedelta(seconds=66),floor=1000)=={}


def test_policy_and_hybrid_signal_do_not_mutate_parents():
    from memetrader.cohort_experiments import cohort_experiment_policies
    from memetrader.trajectory144 import policies as parent_policies
    parent=next(p for p in parent_policies(cohort_experiment_policies()[2]) if p['arm_id']==PARENT)
    original=deepcopy(parent); values=policies(parent)
    assert parent==original and {p['arm_id'] for p in values}==set(ARMS)
    assert all(p['notional_usd']==20 and p['entry_filter']['max_concurrent_positions']==8 for p in values)
    hybrid=next(p for p in values if p['arm_id']==HYBRID)
    assert hybrid['take_profit']==[{'return':.15,'fraction_of_remaining':.5},{'return':.5,'fraction_of_remaining':.5}]
    from test_impulse_retest230 import trigger
    _,signal=trigger(utcnow()); original=deepcopy(signal)
    result=hybrid_signal(signal)[HYBRID]
    assert signal==original and result['recorded_at']==signal['recorded_at']
    assert result['episode_id']==signal['episode_id']
    assert result['decision_key']!=signal['decision_key']


def test_real_store_registers_then_later_buy_partial_sell_and_remaining_writeoff(tmp_path,monkeypatch):
    from memetrader.store import Store
    from memetrader.cohort_experiments import cohort_experiment_policies
    from memetrader.trajectory144 import policies as parent_policies
    from test_l0_store import _snapshot
    clock=[utcnow()]
    for module in ('store','models'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'pressure234.sqlite3',initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.activate_chain_paper_execution(dict(buy_slippage_pct=4,sell_slippage_pct=4,additional_fee_usd_each_fill=0,min_pool_liquidity_usd=1000),activated_at=clock[0])
        parent=next(p for p in parent_policies(cohort_experiment_policies()[2]) if p['arm_id']==PARENT)
        store.append_chain_meme_trader_policy(parent)
        before=store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)['definition_json']
        assert store.register_chain_meme_pressure234()==3
        assert store.register_chain_meme_pressure234()==0
        assert store._chain_meme_trader_registration(store.CHAIN_MEME_TRADER_ACTIVE_VERSION)['definition_json']==before
        at=clock[0]+timedelta(seconds=1)
        _,results=run_sequence(sequence(at)); signals=results[-1]
        clock[0]=at+timedelta(seconds=16)
        token=TokenCandidate('solana',TOKEN.split(':')[1],'Fixture','FIX')
        store.upsert_token(token,seen_at=clock[0])
        assert store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0],price=1.06),recorded_at=clock[0],cohort_signals=signals)==0
        assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions').fetchone()[0]==0
        clock[0]+=timedelta(seconds=2)
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0],price=1.07),recorded_at=clock[0],cohort_signals=signals)
        position=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(YOUNG,)).fetchone()
        assert position is not None and position['stake_usd']==20
        quantity=20/(1.07*1.04)
        assert position['paper_quantity_tokens']==pytest.approx(quantity)
        for price in (1.4,1.42,1.42):
            clock[0]+=timedelta(seconds=2)
            store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0],price=price),recorded_at=clock[0])
            store.evaluate_chain_meme_trader_market_marks(now=clock[0])
        position=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(YOUNG,)).fetchone()
        assert position['status']=='open'
        assert position['remaining_quantity_tokens']==pytest.approx(quantity*.5)
        assert position['realized_proceeds_usd']==pytest.approx(quantity*.5*1.42*.96)
        assert store.db.execute("SELECT count(*) FROM chain_meme_trader_trades WHERE arm_id=? AND side='SELL'",(YOUNG,)).fetchone()[0]==1
        for price in (2.5,2.4):
            clock[0]+=timedelta(seconds=2)
            store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0],price=price),recorded_at=clock[0])
            store.evaluate_chain_meme_trader_market_marks(now=clock[0])
        position=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(YOUNG,)).fetchone()
        assert position['remaining_quantity_tokens']==pytest.approx(quantity*.25)
        proceeds=quantity*.5*1.42*.96+quantity*.25*2.4*.96
        assert position['realized_proceeds_usd']==pytest.approx(proceeds)
        clock[0]+=timedelta(seconds=2)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0],price=.8,liquidity=1),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0])
        position=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(YOUNG,)).fetchone()
        assert position['status']=='written_off' and position['remaining_quantity_tokens']==0
        assert position['realized_pnl_usd']==pytest.approx(proceeds-20)
        net=store.db.execute('SELECT SUM(net_cash_flow_usd) FROM chain_meme_trader_trades WHERE arm_id=?',(YOUNG,)).fetchone()[0]
        assert net==pytest.approx(proceeds-20)
    finally:
        store.close()


def test_hybrid_reuses_real_230_buy_but_exits_independently(tmp_path,monkeypatch):
    from memetrader.store import Store
    from memetrader.cohort_experiments import cohort_experiment_policies
    from memetrader.trajectory144 import policies as parent_policies
    from memetrader.impulse_retest230 import ARMS as OLD_ARMS, aliases
    from test_impulse_retest230 import trigger
    from test_l0_store import _snapshot
    clock=[utcnow()]
    for module in ('store','models'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'hybrid234.sqlite3',initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        parent=next(p for p in parent_policies(cohort_experiment_policies()[2]) if p['arm_id']==PARENT)
        store.append_chain_meme_trader_policy(parent)
        store.register_chain_meme_impulse_retest230()
        store.register_chain_meme_pressure234()
        at=clock[0]+timedelta(seconds=1); _,signal=trigger(at)
        signals={**aliases(signal),**hybrid_signal(signal)}
        clock[0]=at+timedelta(seconds=30)
        token=TokenCandidate('solana',TOKEN.split(':')[1],'Hybrid','HYB')
        store.upsert_token(token,seen_at=clock[0])
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0],price=.94),recorded_at=clock[0],cohort_signals=signals)
        assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions').fetchone()[0]==0
        clock[0]+=timedelta(seconds=2)
        store.observe_chain_meme_pattern(token,_snapshot(token,POOL,clock[0],price=.95),recorded_at=clock[0],cohort_signals=signals)
        positions=[dict(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_positions')]
        assert {p['arm_id'] for p in positions}==set(OLD_ARMS)|{HYBRID}
        assert len({p['source_entry_fill_id'] for p in positions})==1
        assert len({p['opened_at'] for p in positions})==1
        for price in (1.20,1.21):
            clock[0]+=timedelta(seconds=2)
            store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0],price=price),recorded_at=clock[0])
            store.evaluate_chain_meme_trader_market_marks(now=clock[0])
        states={r['arm_id']:dict(r) for r in store.db.execute('SELECT * FROM chain_meme_trader_positions')}
        assert states[OLD_ARMS[0]]['status']=='closed'
        assert states[OLD_ARMS[1]]['status']=='open'
        assert states[HYBRID]['status']=='open'
        assert states[HYBRID]['remaining_quantity_tokens']==pytest.approx(states[OLD_ARMS[1]]['remaining_quantity_tokens']/2)
        assert states[HYBRID]['realized_proceeds_usd']==pytest.approx(20/(.95*1.04)*.5*1.21*.96)
    finally:
        store.close()


def test_state_capacity_and_bad_gaps_never_become_history_replay():
    at=utcnow(); tracker=Tracker(at-timedelta(seconds=1))
    for i in range(530):
        f=frame(at,chain='bsc',token_id='bsc:0x'+format(i,'040x'),pair_address='0x'+format(i+1000,'040x'),pool_age_seconds=22000)
        assert tracker.accept(f,at,floor=1000)=={}
    assert len(tracker.states)==512 and tracker.counts['capacity_evicted']==18
    assert len(tracker.fired)<=2048
