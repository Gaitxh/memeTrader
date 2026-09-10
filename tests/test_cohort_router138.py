from datetime import timedelta
from types import SimpleNamespace
import pytest

from memetrader.cohort_experiments import (
    ROUTER_ARM,
    cohort_experiment_policies,
    routed_cohort_signals,
)
from memetrader.models import TokenCandidate, iso, utcnow
from memetrader.preentry_safety import PreentrySafety
from memetrader.store import Store
from memetrader.narrative_hold import NarrativeHold
from test_l0_store import _snapshot
from test_synthetic_harvest136 import TOKEN, POOL


def _signal(arm, now, key):
    return {
        "episode_id": key,
        "decision_key": key,
        "selected": {"token_id": TOKEN, "pair_address": POOL},
        "observed_at": iso(now),
        "recorded_at": iso(now),
        "decision_evidence": {"signal_at": iso(now)},
    }


def test_router_policy_and_alias_are_preregistered_and_prioritized():
    policies = {policy["arm_id"]: policy for policy in cohort_experiment_policies()}
    router = policies[ROUTER_ARM]
    assert router["notional_usd"] == 5.0
    assert router["entry_filter"]["max_concurrent_positions"] == 4
    assert router["source_arm_ids"] == [
        "organic_reawakening_flow_v1",
        "clone_consensus_leader_v2",
        "organic_early_flow_v1",
    ]
    assert policies["organic_short_observed_flow_v1"]["notional_usd"] == 2.0
    assert policies["organic_short_observed_flow_v1"]["max_hold_minutes"] == 5.0
    now = utcnow()
    routed = routed_cohort_signals({
        "organic_early_flow_v1": _signal("organic_early_flow_v1", now, "early"),
        "clone_consensus_leader_v2": _signal("clone_consensus_leader_v2", now, "clone"),
        "organic_reawakening_flow_v1": _signal("organic_reawakening_flow_v1", now, "reawakening"),
    })[ROUTER_ARM]
    assert routed["decision_evidence"]["router_mode"] == "reawakening"
    assert routed["decision_evidence"]["router_source_arm"] == "organic_reawakening_flow_v1"
    assert routed["decision_key"] == "reawakening|" + ROUTER_ARM


def test_store_admits_router_source_alias_to_claim_and_common_safety_wait(tmp_path, monkeypatch):
    clock = [utcnow()]
    for module in ("store", "models", "preentry_safety", "narrative_hold"):
        monkeypatch.setattr("memetrader." + module + ".utcnow", lambda: clock[0])
    store = Store(tmp_path / "router.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_cohort_experiments()
    token = TokenCandidate("bsc", TOKEN.split(":", 1)[1], "Router", "RTR")
    store.upsert_token(token)
    gate = PreentrySafety(store, SimpleNamespace(config={}))
    store._preentry_safety = gate
    narrative = NarrativeHold(SimpleNamespace(store=store, autonomous_search=SimpleNamespace(config={})))
    signals = {"organic_reawakening_flow_v1": _signal("organic_reawakening_flow_v1", clock[0], "reawakening")}
    for _ in range(2):
        store.observe_chain_meme_pattern(
            token, _snapshot(token, POOL, clock[0]), recorded_at=clock[0], cohort_signals=signals
        )
        clock[0] += timedelta(seconds=1)
    gate.cache[(TOKEN, POOL)] = {"status": "PASS", "allow": True, "source_at": iso(clock[0]), "reasons": []}
    clock[0] += timedelta(seconds=1)
    with store._lock, store.db:
        gate.resume(token, _snapshot(token, POOL, clock[0]), clock[0])
    decision = store.db.execute(
        "SELECT status FROM chain_meme_trader_entry_decisions WHERE arm_id=?", (ROUTER_ARM,)
    ).fetchone()
    assert decision is not None and decision["status"] == "admitted"
    position = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ROUTER_ARM,)).fetchone()
    assert position is not None and position["stake_usd"] == 5.0
    assert not gate.pending
    cohort = store.db.execute(
        "SELECT feature_json FROM chain_meme_trader_v6_cohorts WHERE id=?", (position["shadow_cohort_id"],)
    ).fetchone()
    assert store._json_object(cohort["feature_json"])["cohort_signals"][ROUTER_ARM]["decision_evidence"]["router_mode"] == "reawakening"
    original = int(position["amount_raw"])
    def mark(price, seconds):
        clock[0] += timedelta(seconds=seconds)
        store.upsert_chain_meme_trader_market_mark(token, _snapshot(token, POOL, clock[0], price=price), recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[TOKEN])
    mark(6, 2)
    mark(6, 1)
    position = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (ROUTER_ARM,)).fetchone()
    assert position["principal_recovered"] == 1 and position["realized_proceeds_usd"] >= 5.0
    assert int(position["amount_raw"]) >= original / 2
    narrative.collect()
    assert narrative.state["cases"]
    from test_narrative_hold import TYPES
    case = next(iter(narrative.state['cases'].values()))
    eid = narrative.record(case, 'result', {'state': 'CONFIRMED_EXPANDING'}, clock[0])
    narrative.state['overlay_enabled'] = True
    narrative.state['latest'][case['id']] = dict(**TYPES, state='CONFIRMED_EXPANDING', pool=POOL,
        cutoff=iso(clock[0]), recorded_at=iso(clock[0]), evidence_id=eid)
    narrative.save()
    mark(6, 1801); mark(6, 1)
    assert store.db.execute('SELECT status FROM chain_meme_trader_positions WHERE arm_id=?', (ROUTER_ARM,)).fetchone()[0] == 'open'
    mark(1, 1); mark(1, 1)
    assert store.db.execute('SELECT status FROM chain_meme_trader_positions WHERE arm_id=?', (ROUTER_ARM,)).fetchone()[0] == 'closed'
    store.close()


@pytest.mark.parametrize('source,minutes',[('organic_early_flow_v1',5),('clone_consensus_leader_v2',15)])
def test_router_mechanical_exit_then_new_episode_not_lifetime_block(tmp_path,monkeypatch,source,minutes):
    from test_strategy_delivery137 import setup
    clock,store,token,gate=setup(tmp_path,monkeypatch)
    def count():return store.db.execute('SELECT count(*) FROM chain_meme_trader_positions WHERE arm_id=?',(ROUTER_ARM,)).fetchone()[0]
    def enqueue(key,pool=POOL):
        signal=_signal(source,clock[0],key)
        signal['selected']['pair_address']=pool
        signal['decision_evidence']['frozen_at']=iso(clock[0])
        for _ in range(2):
            store.observe_chain_meme_pattern(token,_snapshot(token,pool,clock[0]),recorded_at=clock[0],cohort_signals={source:signal})
            clock[0]+=timedelta(seconds=1)
    clock[0]+=timedelta(seconds=1);enqueue('first')
    # A separate exact pool cannot reserve a second router position for the token.
    enqueue('second-pool','0x'+'9'*40)
    gate.cache[(TOKEN,POOL)]={'status':'PASS','allow':True,'source_at':iso(clock[0]),'reasons':[]}
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    assert count()==1
    clock[0]+=timedelta(minutes=minutes,seconds=1)
    for _ in range(2):
        store.upsert_chain_meme_trader_market_mark(token,_snapshot(token,POOL,clock[0]),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0],token_ids=[TOKEN])
        clock[0]+=timedelta(seconds=1)
    assert store.db.execute('SELECT status FROM chain_meme_trader_positions WHERE arm_id=?',(ROUTER_ARM,)).fetchone()[0]=='closed'
    enqueue('fresh-after-close')
    clock[0]+=timedelta(seconds=1)
    gate.cache[(TOKEN,POOL)]={'status':'PASS','allow':True,'source_at':iso(clock[0]),'reasons':[]}
    clock[0]+=timedelta(seconds=1)
    with store._lock,store.db:gate.resume(token,_snapshot(token,POOL,clock[0]),clock[0])
    assert count()==2
    store.close()
