from copy import deepcopy
from datetime import timedelta
import json

import pytest

from memetrader.models import TokenCandidate, TokenSnapshot, iso, utcnow
from memetrader.research_finalists import finalist_policies, evaluate_finalist_exit
from memetrader.research_round2 import round2_policies, evaluate_round2_exit, chase_decision
from memetrader.store import Store


def cfg(mechanism):
    return next(p["capital_exit_policy"] for p in round2_policies()
        if p["arm_id"] == f"round2_{mechanism}_candidate_v1")


def evaluate(mechanism, rows, state=None):
    start = utcnow()
    position = dict(token_id="solana:fixture", pair_address="pool", stake_usd=5,
        remaining_quantity_tokens=2, opened_at=iso(start-timedelta(seconds=1)))
    state = deepcopy(state or {})
    if state.get("runner_epoch"):
        state["runner_epoch"]["filled_at"] = iso(start)
        state["runner_observable_since"] = iso(start)
    results = []
    for seconds, extra in rows:
        at = start+timedelta(seconds=seconds)
        frame = dict(frame_id=iso(at), observed_at=iso(at), recorded_at=iso(at),
            token_id=position["token_id"], pair_address="pool", original_pool=True,
            provider="dexscreener", price_usd=1, liquidity_usd=10000,
            economic_value_usd=5, net_recovery_usd=2.5, buys=60, sells=40, volume=1000,
            **{})
        frame.update(extra)
        original = deepcopy(state)
        result = evaluate_round2_exit(position, frame, state, now=at, policy=cfg(mechanism))
        assert state == original
        state = result[2]
        results.append(result)
    return results


def test_chase_budget_is_not_execution_or_profit_proof():
    assert chase_decision(1, 1.04, .04)[0]
    assert not chase_decision(1, 1.041, .04)[0]
    assert chase_decision(1, 2, None)[0]
    assert chase_decision(1, .8, .04)[0]
    assert not chase_decision(None, 1, None)[0]


def test_slow_clock_grants_only_one_small_progress_extension():
    rows = [(s, {"economic_value_usd": 5+s*.0001}) for s in range(0,301,30)]
    out = evaluate("slow_grace", rows)
    assert out[6][0] == "HOLD" and out[6][2]["grace_used"]
    assert out[-1][0] == "SELL"
    flat = evaluate("slow_grace", [(s,{}) for s in range(0,181,30)])
    assert flat[-1][0] == "SELL" and not flat[-1][2].get("grace_used")
    gap = evaluate("slow_grace", rows[:7]+[(300,{})])
    assert gap[-1][0] == "HOLD" and gap[-1][2]["grace_used"]


def test_giveback_uses_observed_duration_cancel_and_gap():
    rows = [(0,{"economic_value_usd":6})]+[(s,{"economic_value_usd":5.5}) for s in range(10,131,30)]
    out = evaluate("giveback_duration",rows)
    assert all(x[0]=="HOLD" for x in out[:-1]) and out[-1][0]=="SELL"
    for field,value in (("economic_value_usd",5.6),("provider","gecko")):
        altered=deepcopy(rows);altered[3][1][field]=value
        assert evaluate("giveback_duration",altered)[-1][0]=="HOLD"
    assert evaluate("giveback_duration",rows[:2]+[(200,{"economic_value_usd":5.4})])[-1][0]=="HOLD"


def test_giveback_control_and_candidate_share_observation_segment_peak():
    at=utcnow()
    pos=dict(token_id="solana:fixture",pair_address="pool",stake_usd=5,
        opened_at=iso(at-timedelta(seconds=1)))
    control=next(p["capital_exit_policy"] for p in round2_policies()
        if p["arm_id"]=="round2_giveback_duration_control_v1")
    states=[{},{}]
    for seconds,value,provider in [(0,7,"dex"),(10,6,"dex"),(20,5.8,"gecko"),(90,5.6,"gecko")]:
        now=at+timedelta(seconds=seconds)
        frame=dict(token_id=pos["token_id"],pair_address="pool",original_pool=True,
            frame_id=iso(now),observed_at=iso(now),recorded_at=iso(now),provider=provider,
            price_usd=value,liquidity_usd=10000,economic_value_usd=value)
        for i,(fn,policy) in enumerate([(evaluate_finalist_exit,control),
                (evaluate_round2_exit,cfg("giveback_duration"))]):
            result=fn(pos,frame,states[i],now=now,policy=policy)
            states[i]=result[2]
        assert states[0]["peak_profit"]==states[1]["peak_profit"]
    assert states[1]["peak_profit"]==pytest.approx(.6)


def test_response_exhaustion_precedes_price_decline_and_rejects_activity_holes():
    rows=[(0,{"price_usd":1,"buys":70,"sells":30}),
        (10,{"price_usd":1.1,"volume":1100,"buys":55,"sells":45}),
        (20,{"price_usd":1.101,"volume":1200,"buys":40,"sells":60})]
    assert evaluate("response_exhaustion",rows)[-1][0]=="SELL"
    for field,value in (("volume",None),("provider","gecko"),("price_usd",1.2),("buys",80)):
        altered=deepcopy(rows);altered[-1][1][field]=value
        assert evaluate("response_exhaustion",altered)[-1][0]=="HOLD"
    noise=deepcopy(rows)
    noise[1][1]["price_usd"]=1.000001
    noise[2][1]["price_usd"]=1.000001
    assert evaluate("response_exhaustion",noise)[-1][0]=="HOLD"


def test_runner_requires_real_partial_and_new_fixed_quantity_progress():
    rows=[(s,{}) for s in range(0,211,30)]
    assert all(r[0]=="HOLD" for r in evaluate("runner_requalification",rows))
    state={"runner_epoch":{"fill_id":1,"quantity_tokens":2,"net_value_usd":2.5,
        "remaining_cost_usd":2.5,"liquidity_usd":10000}}
    assert evaluate("runner_requalification",rows,state)[6][0]=="SELL"
    qualified=deepcopy(rows);qualified[2][1]["net_recovery_usd"]=2.526
    assert all(r[0]=="HOLD" for r in evaluate("runner_requalification",qualified,state))
    assert evaluate("runner_requalification",rows[:2]+[(190,{})],state)[-1][0]=="HOLD"


def test_duplicate_future_and_identity_cannot_advance_new_exit():
    for mechanism in ("slow_grace","giveback_duration","response_exhaustion","runner_requalification"):
        out=evaluate(mechanism,[(0,{}),(0,{}),(10,{"pair_address":"wrong"}),
            (20,{"observed_at":iso(utcnow()+timedelta(days=1))})])
        assert [r[0] for r in out]==["HOLD","WAIT","WAIT","WAIT"]


@pytest.mark.parametrize("mechanism",["slow_grace","giveback_duration","response_exhaustion"])
def test_new_exit_reaches_real_pending_and_later_paper_sell(tmp_path,monkeypatch,mechanism):
    clock=[utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow",lambda:clock[0])
    monkeypatch.setattr("memetrader.models.utcnow",lambda:clock[0])
    store=Store(tmp_path/"exit.sqlite3",initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_research_round2()
    version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    token=TokenCandidate("solana","exit-fixture","Fixture")
    created=round((clock[0]-timedelta(seconds=180)).timestamp()*1000)
    def snap(price=1,buys=60,volume=1000):
        return TokenSnapshot("solana",token.address,price,10000,100000,volume,buys,100-buys,
            observed_at=clock[0],ingested_at=clock[0],provider="dexscreener",
            raw={"pair":{"chainId":"solana","pairAddress":"pool","pairCreatedAt":created,
                "baseToken":{"address":token.address},"priceUsd":str(price)}})
    for _ in range(2):
        clock[0]+=timedelta(seconds=16)
        store.observe_chain_meme_pattern(token,snap(),recorded_at=clock[0])
    arm=f"round2_{mechanism}_candidate_v1"
    get=lambda:store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?",(arm,)).fetchone()
    if mechanism=="slow_grace":
        rows=[(30,1+i*.0001,60,1000) for i in range(11)]
    elif mechanism=="giveback_duration":
        rows=[(20,1.31,60,1000)]+[(30,1.18,60,1000)]*5
    else:
        rows=[(10,1,70,1000),(10,1.1,55,1100),(10,1.1001,40,1200)]
    for dt,price,buys,volume in rows:
        clock[0]+=timedelta(seconds=dt)
        store.upsert_chain_meme_trader_market_mark(token,snap(price,buys,volume),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=clock[0],token_ids=[token.token_id])
    assert get()["pending_mark_id"] is not None and get()["status"]=="open"
    assert f"round2_{mechanism}" in store.db.execute("SELECT reason FROM chain_meme_trader_marks WHERE id=?",(get()["pending_mark_id"],)).fetchone()[0]
    clock[0]+=timedelta(seconds=10)
    store.upsert_chain_meme_trader_market_mark(token,snap(price,buys,volume),recorded_at=clock[0])
    store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=clock[0],token_ids=[token.token_id])
    assert get()["status"]=="closed"
    assert get()["realized_pnl_usd"]==pytest.approx(5/1.04*price*.96-5)
    store.close()


@pytest.mark.parametrize("chain",["solana","bsc","robinhood"])
def test_registry_pairs_chase_no_replay_and_actual_partial_epoch(tmp_path,monkeypatch,chain):
    clock=[utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow",lambda:clock[0])
    monkeypatch.setattr("memetrader.models.utcnow",lambda:clock[0])
    store=Store(tmp_path/"round2.sqlite3",initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    store.register_chain_meme_research_finalists()
    before=[tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions")]
    old=deepcopy(finalist_policies())
    assert store.register_chain_meme_research_round2()==10
    assert store.register_chain_meme_research_round2()==0
    assert old==finalist_policies()
    assert before==[tuple(r) for r in store.db.execute("SELECT * FROM chain_meme_trader_policy_additions WHERE arm_id NOT LIKE 'round2_%'")]
    token=TokenCandidate(chain,"fixture" if chain=="solana" else "0x"+"ab"*20,"Fixture")
    pair="pool" if chain=="solana" else "0x"+"cd"*20
    created=round((clock[0]-timedelta(seconds=180)).timestamp()*1000)
    def snap(price=1):
        return TokenSnapshot(chain,token.address,price,10000,100000,2000,15,5,
            observed_at=clock[0],ingested_at=clock[0],provider="dexscreener",
            raw={"pair":{"chainId":chain,"pairAddress":pair,"pairCreatedAt":created,
                "baseToken":{"address":token.address},"priceUsd":str(price)}})
    clock[0]+=timedelta(seconds=1)
    assert store.observe_chain_meme_pattern(token,snap(),recorded_at=clock[0])==0
    clock[0]+=timedelta(seconds=16)
    assert store.observe_chain_meme_pattern(token,snap(1.1),recorded_at=clock[0])==14 # old5 + new9
    positions=store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'round2_%'").fetchall()
    assert len(positions)==9 and len({p["source_entry_fill_id"] for p in positions})==1
    clock[0]+=timedelta(seconds=16)
    assert store.observe_chain_meme_pattern(token,snap(1),recorded_at=clock[0])==0
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id='round2_chase_candidate_v1'").fetchone()[0]==0
    get=lambda role:store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?",
        (f"round2_runner_requalification_{role}_v1",)).fetchone()
    version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    for i in range(2):
        clock[0]+=timedelta(seconds=10)
        store.upsert_chain_meme_trader_market_mark(token,snap(1.6),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=clock[0],token_ids=[token.token_id])
        if i==0:
            assert get("candidate")["pending_mark_id"] is not None
            assert not json.loads(get("candidate")["capital_exit_state_json"] or "{}").get("runner_epoch")
    p=get("candidate");state=json.loads(p["capital_exit_state_json"])
    assert p["next_tp_index"]==1 and p["principal_recovered"]==0
    assert state["runner_epoch"]["fill_id"]==p["last_fill_id"]
    assert state["runner_epoch"]["quantity_tokens"]==p["remaining_quantity_tokens"]
    assert state["runner_epoch"]["remaining_cost_usd"]==pytest.approx(2.5)
    assert p["realized_proceeds_usd"]==pytest.approx(get("control")["realized_proceeds_usd"])
    # No runner progress; the candidate arms at the observable deadline, then a later receipt fills.
    for _ in range(6):
        clock[0]+=timedelta(seconds=30)
        store.upsert_chain_meme_trader_market_mark(token,snap(1.6),recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=clock[0],token_ids=[token.token_id])
    assert get("candidate")["status"]=="open" and get("candidate")["pending_mark_id"] is not None
    clock[0]+=timedelta(seconds=10)
    store.upsert_chain_meme_trader_market_mark(token,snap(1.6),recorded_at=clock[0])
    store.evaluate_chain_meme_trader_market_marks(definition_version=version,now=clock[0],token_ids=[token.token_id])
    assert get("candidate")["status"]=="closed" and get("control")["status"]=="open"
    store.close()
