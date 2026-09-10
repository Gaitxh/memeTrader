from datetime import timedelta
from types import SimpleNamespace
import pytest
from memetrader.models import utcnow,iso,TokenCandidate
from memetrader.store import Store
from memetrader.preentry_safety import PreentrySafety
from test_l0_store import _snapshot


@pytest.mark.parametrize('arm,origin,stake',[
    ('clone_consensus_leader_v2','frozen_at',5),
    ('organic_early_flow_v1','signal_at',2),
    ('organic_reawakening_flow_v1','signal_at',5),
    ('event_clone_narrative_reawakening_v1','event_recorded_at',5)])
def test_funded_cohort_frontier_safety_next_frame_and_once(tmp_path,monkeypatch,arm,origin,stake):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    store=Store(tmp_path/'cohort.sqlite3',initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_cohort_experiments()
    assert store.register_chain_meme_cohort_experiments()==0
    token=TokenCandidate('bsc','0x'+'12'*20,'Coin','C');pool='0x'+'34'*20
    store.upsert_token(token)
    gate=PreentrySafety(store,SimpleNamespace(config={}));store._preentry_safety=gate
    clock[0]+=timedelta(seconds=1)
    signal={arm:dict(episode_id='new',decision_key='new|'+arm,
        selected=dict(token_id=token.token_id,pair_address=pool),observed_at=iso(clock[0]),recorded_at=iso(clock[0]),
        decision_evidence={origin:iso(clock[0]-timedelta(days=1))})}
    store.observe_chain_meme_pattern(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0],cohort_signals=signal)
    assert not gate.pending  # Pre-frontier event cannot enter a newly funded arm.
    clock[0]+=timedelta(seconds=1)
    signal[arm].update(observed_at=iso(clock[0]),recorded_at=iso(clock[0]),decision_evidence={origin:iso(clock[0])})
    if arm=='event_clone_narrative_reawakening_v1':
        from memetrader.event_clone_shadow import EventCloneShadow
        shadow=EventCloneShadow(store);at=clock[0]
        source=dict(url='https://example.org/event',event_key='fresh-event',
            published_at=iso(at-timedelta(seconds=2)),available_at=iso(at-timedelta(seconds=1)),
            source_evidence_id=41,scout_model='gpt-5.6-luna')
        result=dict(state='CONFIRMED_EXPANDING',narrative_type='real_event_novelty',promotion_only=False,
            independent_origin_count=2,event_key='fresh-event',token_binding_basis='verified_exact_contract_frozen_cohort',
            cutoff=iso(at),research_mode='VERIFY_PERSISTED_SOURCES',scout_metadata={},scout_sources=[source],
            verifier=dict(model='gpt-5.6-terra',status='cross_source_supported',claim_status='confirmed_fact',confidence=.9))
        shadow.receive('narrative_hold_result_v2',result,token.token_id,pool,99,at)
        for _ in range(2):
            clock[0]+=timedelta(seconds=2)
            shadow.frame(token,_snapshot(token,pool,clock[0]),clock[0],{})
        signal={};signal.update(shadow.signals_for(token.token_id,pool,clock[0]))
        assert arm in signal  # Exact runtime dict.update envelope into the real Store below.
    for _ in range(3):
        store.observe_chain_meme_pattern(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0],cohort_signals=signal)
        clock[0]+=timedelta(seconds=1)
    assert len(gate.pending)==1
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]==0
    gate.cache[(token.token_id,pool)]=dict(status='PASS',allow=True,source_at=iso(clock[0]),reasons=[])
    with store._lock,store.db:gate.resume(token,_snapshot(token,pool,clock[0]),clock[0])
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]==0
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,pool,clock[0]),clock[0])
    rows=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchall()
    assert len(rows)==1 and rows[0]['stake_usd']==stake
    for _ in range(2):
        clock[0]+=timedelta(seconds=1)
        store.observe_chain_meme_pattern(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0],cohort_signals=signal)
    assert store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]==1
    # Common original-pool mechanical exit, no Agent or separate native fill path.
    for _ in range(2):
        clock[0]+=timedelta(seconds=2)
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,pool,clock[0],price=.5),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(definition_version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
            now=clock[0],token_ids=[token.token_id])
    position=store.db.execute('SELECT * FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()
    assert position['status']=='closed' and position['realized_pnl_usd']<0
    store.close()
