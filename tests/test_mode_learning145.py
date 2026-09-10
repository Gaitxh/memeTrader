from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
import pytest

from memetrader import mode_learning144 as v3
from memetrader import mode_learning145 as v4
from memetrader.models import TokenSnapshot, iso, parse_time, utcnow
from memetrader.store import Store
from memetrader.trajectory144 import ARMS


NOW = utcnow()
CONTRACT = {"feature": "trajectory144/v1", "costs": {}, "horizons": [5, 15, 30, 60]}
ADDRESS = "0x" + "12" * 20
PAIR = "0x" + "34" * 20
TOKEN_ID = f"bsc:{ADDRESS}"


def _state():
    return v4.initialize(now=NOW, contract=CONTRACT)


def _capture(state, key="episode", *, at=NOW):
    return v3.capture(
        state,
        episode_key=key,
        token_id=TOKEN_ID,
        pair_address=PAIR,
        chain="bsc",
        age_bucket="0_300",
        mode="trajectory144_sparse_peer_hot_fast_v1",
        features={"contract": "frozen"},
        decision_at=iso(at),
        observed_at=iso(at),
        ingested_at=iso(at),
        recorded_at=iso(at),
        signal=True,
    )


def _frame(at, *, price=1.0, liquidity=2000.0):
    return {
        "token_id": TOKEN_ID,
        "pair_address": PAIR,
        "observed_at": iso(at),
        "ingested_at": iso(at),
        "recorded_at": iso(at),
        "price_usd": price,
        "liquidity_usd": liquidity,
    }


def _sealed_model(state, *, releases=2):
    model = {
        "version": "finite/v5:test",
        "cutoff_at": iso(NOW),
        "training_frontier": 0,
        "contract_hash": state["contract_hash"],
        "selected_groups": ["bsc|0_300|trajectory144_sparse_peer_hot_fast_v1|5"],
        "selection_scores": {"bsc|0_300|trajectory144_sparse_peer_hot_fast_v1|5": 0.2},
        "releases": releases,
        "estimates": {},
    }
    model["seal"] = v4.digest(model)
    return model


def _snapshot(at, *, price=1.0, liquidity=2000.0):
    return TokenSnapshot(
        "bsc", ADDRESS, price, liquidity, 2000.0, 10.0, 1, 1,
        observed_at=at,
        raw={"pair": {"chainId": "bsc", "pairAddress": PAIR,
                      "baseToken": {"address": ADDRESS}}},
    )


def test_v4_capture_observe_train_is_json_safe_and_keeps_prequential_prediction():
    state = _state()
    captured = _capture(state)
    assert captured["status"] == "captured"
    assert captured["episode"]["prediction"]["model_version"] == v3.BASELINE
    assert state["horizons"] == [5, 15, 30, 60]

    v3.observe(state, episode_key="episode", frame=_frame(NOW + timedelta(seconds=1)), now=NOW + timedelta(seconds=1))
    for minute in range(1, 5):
        v3.observe(state, episode_key="episode", frame=_frame(NOW + timedelta(minutes=minute)), now=NOW + timedelta(minutes=minute))
    result = v3.observe(state, episode_key="episode", frame=_frame(NOW + timedelta(minutes=5, seconds=1), price=1.3), now=NOW + timedelta(minutes=5, seconds=1))
    assert result["labels"][0]["status"] == "OBSERVED"
    learned = v4.train(state, cutoff_at=NOW + timedelta(minutes=5, seconds=1))
    assert learned["consumed"] == 1
    assert state["groups"]["bsc|0_300|trajectory144_sparse_peer_hot_fast_v1|5"]["events"][0]["status"] == "OBSERVED"
    assert json.loads(json.dumps(state))["episodes"]["episode"]["prediction"]["model_version"] == v3.BASELINE


def test_v4_horizons_are_post_activation_and_each_label_is_consumed_once():
    state = _state()
    assert parse_time(state["activated_at"]) == NOW
    _capture(state, at=NOW + timedelta(seconds=1))
    v3.observe(state, episode_key="episode", frame=_frame(NOW + timedelta(seconds=2)), now=NOW + timedelta(seconds=2))
    labels = v3.observe(state, episode_key="episode", frame=_frame(NOW + timedelta(minutes=60, seconds=3)), now=NOW + timedelta(minutes=60, seconds=3))["labels"]
    assert {label["horizon"] for label in labels} == set(v4.HORIZONS)
    first = v4.train(state, cutoff_at=NOW + timedelta(minutes=60, seconds=3))
    second = v4.train(state, cutoff_at=NOW + timedelta(minutes=60, seconds=3))
    assert first["consumed"] == 4
    assert second["consumed"] == 0


def test_floor_model_event_is_distinct_from_missing_quote_unknown(tmp_path):
    store = Store(tmp_path / "learning.sqlite3", initial_cash_usd=1000)
    coordinator = v4.Coordinator(store)
    start = parse_time(coordinator.state["activated_at"]) + timedelta(seconds=1)
    for key in ("floor",):
        assert _capture(coordinator.state, key, at=start)["status"] == "captured"
        coordinator.reindex()
        coordinator.observe(TOKEN_ID, _snapshot(start + timedelta(seconds=1)), start + timedelta(seconds=1), start + timedelta(seconds=1))
    coordinator.observe(TOKEN_ID, _snapshot(start + timedelta(seconds=2), liquidity=500), start + timedelta(seconds=2), start + timedelta(seconds=2))
    coordinator.observe(TOKEN_ID, _snapshot(start + timedelta(minutes=5, seconds=2)), start + timedelta(minutes=5, seconds=2), start + timedelta(minutes=5, seconds=2))
    floor = coordinator.state["episodes"]["floor"]["results"]["5"]
    assert floor["status"] == "MODEL_FLOOR_EVENT"
    assert floor["source"] == "sampled_model_floor_event_not_fill"
    floor_events = sum(event.get("status") == "MODEL_FLOOR_EVENT" for event in coordinator.state["events"])
    coordinator.observe(TOKEN_ID, _snapshot(start + timedelta(minutes=5, seconds=3)), start + timedelta(minutes=5, seconds=3), start + timedelta(minutes=5, seconds=3))
    assert coordinator.state["episodes"]["floor"]["results"]["5"]["status"] == "MODEL_FLOOR_EVENT"
    assert sum(event.get("status") == "MODEL_FLOOR_EVENT" for event in coordinator.state["events"]) == floor_events

    # A separate identity with no usable endpoint remains UNKNOWN, never a floor event.
    unknown = _capture(coordinator.state, "unknown", at=start)["episode"]
    unknown["entry"] = {**_frame(start), "observed_at": iso(start)}
    v3.expire(coordinator.state, now=start + timedelta(minutes=6, seconds=31))
    assert unknown["results"]["5"]["status"] == "UNKNOWN"
    store.close()


def test_rolling_256_window_keeps_observed_and_unknown_on_one_denominator():
    state = _state()
    group = {"events": [{"status": "UNKNOWN", "token": f"old-{i}", "date": "2026-01-01", "return": None} for i in range(255)] + [{"status": "OBSERVED", "token": "new", "date": "2026-01-02", "return": 0.1}]}
    first = v4.statistics(group)
    group["events"] = (group["events"] + [{"status": "OBSERVED", "token": f"new-{i}", "date": "2026-01-03", "return": 0.1} for i in range(255)])[-256:]
    second = v4.statistics(group)
    assert first["n"] + first["unknown"] == 256
    assert second["n"] + second["unknown"] == 256
    assert second["unknown"] == 0


def test_unpublished_or_empty_train_cannot_mutate_a_sealed_model():
    state = _state()
    state["model"] = _sealed_model(state)
    before = deepcopy(state["model"])
    result = v4.train(state, cutoff_at=NOW)
    assert result == {"consumed": 0, "promoted": False, "dirty_groups": 0}
    assert state["model"] == before


def test_rollback_after_two_releases_is_baseline_and_new_orders_only():
    state = _state()
    state["model"] = _sealed_model(state, releases=2)
    receipt = v4.rollback(state, reason="fixture economic failure", frontier=17, now=NOW)
    assert receipt["affects"] == "new_orders_only"
    assert state["model"]["version"] == v3.BASELINE
    assert state["model"]["releases"] == 2
    assert state["rollback_history"][-1]["observation_frontier"] == 17


def test_train_is_limited_to_64_labels_and_coordinator_reloads_128_pending_index(tmp_path):
    state = _state()
    for number in range(65):
        key = f"limited-{number}"
        episode = _capture(state, key)["episode"]
        episode["results"] = {"5": {"status": "UNKNOWN", "available_at": iso(NOW), "costed_return": None}}
    assert v4.train(state, cutoff_at=NOW)["consumed"] == 64

    store = Store(tmp_path / "reload.sqlite3", initial_cash_usd=1000)
    coordinator = v4.Coordinator(store)
    at = parse_time(coordinator.state["activated_at"]) + timedelta(seconds=1)
    for number in range(128):
        assert coordinator.capture_episode(**{
            "episode_key": f"pending-{number}", "token_id": TOKEN_ID, "pair_address": PAIR,
            "chain": "bsc", "age_bucket": "0_300", "mode": "fixture", "features": {},
            "decision_at": iso(at), "observed_at": iso(at), "ingested_at": iso(at), "recorded_at": iso(at),
        })["status"] == "captured"
    assert coordinator.capture_episode(**{
        "episode_key": "overflow", "token_id": TOKEN_ID, "pair_address": PAIR,
        "chain": "bsc", "age_bucket": "0_300", "mode": "fixture", "features": {},
        "decision_at": iso(at), "observed_at": iso(at), "ingested_at": iso(at), "recorded_at": iso(at),
    })["status"] == "pending_capacity"
    store.set_kv(coordinator.key, coordinator.state)
    restored = v4.Coordinator(store)
    assert len(restored.state["episodes"]) == 128
    assert len(restored.pending_index[(TOKEN_ID, PAIR)]) == 128
    store.close()


def test_known_floor_survives_expiry_without_later_market_frame(tmp_path):
    store=Store(tmp_path/'floor_expired.sqlite3',initial_cash_usd=1000)
    c=v4.Coordinator(store);start=parse_time(c.state['activated_at'])+timedelta(seconds=1)
    c.capture_episode(episode_key='floor-expire',token_id=TOKEN_ID,pair_address=PAIR,chain='bsc',age_bucket='0_300',mode='fixture',features={},decision_at=iso(start),observed_at=iso(start),ingested_at=iso(start),recorded_at=iso(start))
    for second,liq in ((1,2000),(2,10)):
        at=start+timedelta(seconds=second);c.observe(TOKEN_ID,_snapshot(at,liquidity=liq),at,at)
    status=c.flush(start+timedelta(minutes=7))
    assert c.state['episodes']['floor-expire']['results']['5']['status']=='MODEL_FLOOR_EVENT'
    assert status['horizons']['5']['MODEL_FLOOR_EVENT']==1
    assert status['horizons']['5']['UNKNOWN']==0
    store.close()


def test_existing317_routes_legacy_model_not_v4_and_keeps_separate_status(tmp_path):
    store=Store(tmp_path/'contracts.sqlite3',initial_cash_usd=1000)
    c=v4.Coordinator(store)
    c.state['model']=_sealed_model(c.state,releases=1)
    at=parse_time(c.state['activated_at'])+timedelta(seconds=1)
    features={**_frame(at),'chain':'bsc','pool_age_seconds':30}
    signals={arm:dict(decision_key='original:'+arm,observed_at=iso(at),recorded_at=iso(at),decision_evidence={})
             for arm in (ARMS[1],ARMS[4])}
    before=deepcopy(signals)
    output=c.signals(features,signals,at)
    evidence=output[ARMS[5]]['decision_evidence']
    assert evidence['learning_source_arm']==ARMS[4]
    assert evidence['learning_model']==c.legacy.state['model']
    assert evidence['fixed_priority_source_arm']==ARMS[4]
    assert evidence['fixed_priority_decision_key']==signals[ARMS[4]]['decision_key']
    assert next(iter(c.state['selections'].values()))['decision_evidence']['learning_source_arm']==ARMS[1]
    assert signals==before
    assert c.legacy.state.get('horizons',list(v3.HORIZONS))==list(v3.HORIZONS)
    status=c.flush(at)
    assert status['schema']==v4.KEY and status['decision_eligible'] is True
    assert status['trading_selector_contract']==v4.KEY
    assert output[v4.ROUTER]['decision_evidence']['learning_source_arm']==ARMS[1]
    assert output[v4.ROUTER]['decision_key']!=output[ARMS[5]]['decision_key']
    assert c.legacy_status['schema']==v3.KEY
    assert '30' not in c.legacy_status['horizons']
    restored=v4.Coordinator(store)
    assert restored.signals(features,signals,at)[ARMS[5]]==output[ARMS[5]]
    assert restored.legacy.state['model']==c.legacy.state['model']
    store.close()


def _actual_pair(state):
    terms=dict(stake_usd=2.,paper_quantity_tokens=1.,entry_execution_price_usd=2.,opened_at=iso(NOW))
    baseline=dict(version='test',arm=ARMS[4],token_id=TOKEN_ID,pair_address=PAIR,source_fill_id=19,
        entry_terms=terms,decision_key='baseline-episode',realized_pnl_usd=.3)
    router={**deepcopy(baseline),'arm':v4.ROUTER,'model_version':state['model']['version'],
        'baseline_arm':ARMS[4],'baseline_decision_key':'baseline-episode',
        'source_arm':ARMS[1],'decision_key':'selected-episode|router','realized_pnl_usd':-.4}
    state['actual_groups']={v4.ROUTER:[router],ARMS[4]:[baseline]}
    return router,baseline


@pytest.mark.parametrize('missing',['baseline_arm','decision_key','pair','quantity','fill','opened'])
def test_economic_comparison_requires_frozen_actual_equal_entry_baseline(missing):
    state=_state();state['model']=_sealed_model(state)
    router,baseline=_actual_pair(state)
    if missing=='baseline_arm':router.pop('baseline_arm')
    elif missing=='decision_key':baseline['decision_key']='different'
    elif missing=='pair':baseline['pair_address']='other'
    elif missing=='quantity':baseline['entry_terms']['paper_quantity_tokens']=.9
    elif missing=='fill':baseline['source_fill_id']=20
    else:baseline['entry_terms']['opened_at']=iso(NOW+timedelta(seconds=1))
    # The selected source with identical PnL must never act as a fallback baseline.
    state['actual_groups'][ARMS[1]]=[deepcopy(router)]
    pairs,status=v4.matched_baseline(state)
    assert pairs==[] and status['status']=='NO_MATCHED_BASELINE'
    assert status['router_minus_baseline_usd'] is None


def test_equal_fill_fixed_priority_comparison_can_have_negative_delta():
    state=_state();state['model']=_sealed_model(state)
    router,baseline=_actual_pair(state)
    state['actual_groups'][v4.ROUTER].append(deepcopy(router))
    pairs,status=v4.matched_baseline(state)
    assert len(pairs)==1  # Duplicate account/receipt is not another opportunity.
    assert status['router_minus_baseline_usd']==pytest.approx(-.7)


def test_rollback_cannot_republish_same_evidence_after_flush_or_restart():
    state=_state();state['model']=_sealed_model(state,releases=1)
    key=state['model']['selected_groups'][0]
    state['groups'][key]={'events':[dict(status='OBSERVED',token=f't{i}',date=f'2026-09-0{1+i%2}',return_=.2) for i in range(20)]}
    for e in state['groups'][key]['events']:e['return']=e.pop('return_')
    state['group_summaries'][key]=v4.statistics(state['groups'][key])
    state['dispositions'][key]={'missing':[],'status':'ECONOMIC_REVIEW_ELIGIBLE'}
    state['group_label_frontiers']={key:20}
    state['group_last_label_at']={key:iso(NOW)}
    v4.rollback(state,reason='actual loss',frontier=10,now=NOW)
    def mature(s,episode,at,mode=None):
        e=_capture(s,episode,at=at)['episode']
        if mode:e['mode']=mode
        e['results']['5']=dict(status='OBSERVED',costed_return=.2,available_at=iso(at))
    mature(state,'same-flush',NOW)
    assert not v4.train(state,cutoff_at=NOW)['promoted']
    assert state['dispositions'][key]['status']=='ROLLBACK_WAIT_FRESH_EVIDENCE'
    state=json.loads(json.dumps(state))
    later=NOW+timedelta(seconds=1)
    mature(state,'unrelated',later,mode='other')
    assert not v4.train(state,cutoff_at=later)['promoted']
    mature(state,'new-evidence',later)
    assert not v4.train(state,cutoff_at=later)['promoted']
    for i in range(20):
        at=later+timedelta(days=i%2,seconds=i+1)
        mature(state,'new-evidence'+str(i),at)
        state['episodes']['new-evidence'+str(i)]['token_id']='bsc:'+str(i)
    assert v4.train(state,cutoff_at=later+timedelta(days=2))['promoted']
    assert state['model']['version']!='finite/v5:test'
    # A later failure cannot restore a previously rejected model.
    state['previous_models'].append(_sealed_model(state,releases=1))
    v4.rollback(state,reason='second loss',frontier=11,now=later)
    assert state['model']['version']==v3.BASELINE


def test_legacy_and_research_pending_share_existing128_budget(tmp_path):
    store=Store(tmp_path/'shared.sqlite3',initial_cash_usd=1000)
    c=v4.Coordinator(store);at=parse_time(c.state['activated_at'])+timedelta(seconds=1)
    args=dict(token_id=TOKEN_ID,pair_address=PAIR,chain='bsc',age_bucket='0_300',mode='fixture',features={},
        decision_at=iso(at),observed_at=iso(at),ingested_at=iso(at),recorded_at=iso(at))
    for i in range(128):
        consumer=c if i%2 else c.legacy
        assert consumer.capture_episode(episode_key=str(i),**args)['status']=='captured'
    assert c.capture_episode(episode_key='v4-overflow',**args)['status']=='pending_capacity'
    assert c.legacy.capture_episode(episode_key='v3-overflow',**args)['status']=='pending_capacity'
    assert len(c.state['episodes'])+len(c.legacy.state['episodes'])==128
    store.close()
