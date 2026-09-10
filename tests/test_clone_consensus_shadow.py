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
    store.close()
