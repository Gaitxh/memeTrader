import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
import pytest
from memetrader.store import Store
from memetrader.models import TokenCandidate,utcnow,iso
from memetrader.preentry_safety import PreentrySafety
from memetrader.cohort_enrollment import claim_decisions
from test_l0_store import _snapshot

ARM='clone_liquidity_leader_v1'


@pytest.mark.parametrize('verdict',['PASS','REJECT'])
def test_multibatch_security_wait_restart_has_one_cohort(tmp_path,monkeypatch,verdict):
    clock=[utcnow()]
    for module in ('store','models','preentry_safety'):
        monkeypatch.setattr('memetrader.'+module+'.utcnow',lambda:clock[0])
    path=tmp_path/'claims.sqlite3';store=Store(path,initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period();store.register_chain_meme_cohort_experiments()
    token=TokenCandidate('bsc','0x'+'12'*20,'Clone','C');pool='0x'+'34'*20
    store.upsert_token(token);clock[0]+=timedelta(seconds=1)
    signal={ARM:dict(episode_id='frozen',decision_key='frozen|'+ARM,
        selected=dict(token_id=token.token_id,pair_address=pool),observed_at=iso(clock[0]),recorded_at=iso(clock[0]))}
    gate=PreentrySafety(store,SimpleNamespace(config={}));store._preentry_safety=gate
    for _ in range(4):
        assert store.observe_chain_meme_pattern(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0],cohort_signals=signal)==0
        clock[0]+=timedelta(seconds=1)
    assert len(gate.pending)==1
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_v6_cohorts').fetchone()[0]==1
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_cohort_enrollment_claims').fetchone()[0]==1
    store.close()
    store=Store(path,initial_cash_usd=1000);gate=PreentrySafety(store,SimpleNamespace(config={}));store._preentry_safety=gate
    assert len(gate.pending)==1
    gate.cache[(token.token_id,pool)]=dict(status=verdict,allow=verdict=='PASS',source_at=iso(clock[0]),reasons=['fixture'] if verdict=='REJECT' else [])
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,pool,clock[0]),clock[0])
    for _ in range(3):
        clock[0]+=timedelta(seconds=1)
        store.observe_chain_meme_pattern(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0],cohort_signals=signal)
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_v6_cohorts').fetchone()[0]==1
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions').fetchone()[0]==(1 if verdict=='PASS' else 0)
    if verdict=='PASS':
        from memetrader.cohort_enrollment import ANNOTATION_KEY,annotation_id
        version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        cohort=store.db.execute('SELECT shadow_cohort_id FROM chain_meme_trader_positions').fetchone()[0]
        before=Store.chain_meme_trader_summary_from_connection(store.db,arm_id=ARM)['strategies'][0]['account']
        store.set_kv(ANNOTATION_KEY+version,{'positions':{annotation_id(ARM,cohort):{'reason':'duplicate-opportunity-contamination'}}})
        after=Store.chain_meme_trader_summary_from_connection(store.db,arm_id=ARM)['strategies'][0]['account']
        assert before['cash_usd']==after['cash_usd'] and before['realized_pnl_usd']==after['realized_pnl_usd']
        assert after['research_metrics_eligible'] is False and after['engineering_anomaly_position_count']==1
    if verdict=='REJECT':
        claim=store.db.execute('SELECT * FROM chain_meme_cohort_enrollment_claims').fetchone()
        assert claim['terminal_reason']=='REJECT'
        with store.db:assert claim_decisions(store.db,claim['definition_version'],claim['cohort_id'],token.token_id,iso(clock[0]))==[]
    store.close()


def test_atomic_claim_independent_connections_and_legacy_pending(tmp_path):
    path=tmp_path/'race.sqlite3';s=Store(path,initial_cash_usd=1000);version=s.CHAIN_MEME_TRADER_ACTIVE_VERSION
    # Old waiting cohorts without claims reproduce the historical resume race.
    with s.db:
        for cid,arm,key in [(1,'a','episode1'),(2,'a','episode1'),(3,'b','episode1'),(4,'a','episode2')]:
            f=dict(event_keys={arm:key},cohort_signals={arm:dict(decision_key=key)})
            s.db.execute("INSERT INTO chain_meme_trader_v6_cohorts(id,definition_version,token_id,entry_family,source_snapshot_id,pair_address,decided_at,episode_no,feature_json) VALUES(?,?,?,'broad_launch',?,'pool',?,?,?)",
                (cid,version,'bsc:t',cid,iso(),cid,json.dumps(f)))
            s.db.execute("INSERT INTO chain_meme_trader_entry_decisions(definition_version,arm_id,shadow_cohort_id,token_id,baseline_quote_result_id,decided_at,status,reason) VALUES(?,?,?,'bsc:t',?,?,'admitted','fixture')",(version,arm,cid,cid,iso()))
    s.close()
    def attempt(cid):
        db=sqlite3.connect(path,timeout=10);db.row_factory=sqlite3.Row
        with db:result=claim_decisions(db,version,cid,'bsc:t',iso())
        db.close();return cid,bool(result)
    with ThreadPoolExecutor(max_workers=2) as pool:results=dict(pool.map(attempt,[2,1]))
    assert results=={1:True,2:False}
    assert attempt(3)[1] and attempt(4)[1]  # arms and episodes are independent
    assert attempt(2)==(2,False)  # restart/readback cannot replace ownership
    s=Store(path,initial_cash_usd=1000);gate=PreentrySafety(s,SimpleNamespace(config={}))
    with s.db:
        gate.record(dict(version=version,token_id='bsc:t',pool='pool',cohort_id=4),'WAIT_QUEUE_CAPACITY')
        assert claim_decisions(s.db,version,4,'bsc:t',iso())==[]
    assert s.db.execute('SELECT terminal_reason FROM chain_meme_cohort_enrollment_claims WHERE cohort_id=4').fetchone()[0]=='WAIT_QUEUE_CAPACITY'
    s.close()
