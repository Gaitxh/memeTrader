import json
from datetime import timedelta

import pytest

from memetrader.models import TokenCandidate, TokenSnapshot, utcnow
from memetrader.store import Store


def setup_store(tmp_path, monkeypatch):
    clock = [utcnow()]
    monkeypatch.setattr("memetrader.store.utcnow", lambda: clock[0])
    monkeypatch.setattr("memetrader.models.utcnow", lambda: clock[0])
    store = Store(tmp_path / "resource.sqlite3", initial_cash_usd=1000)
    store.activate_chain_meme_trader_funded_period()
    return store, clock


def quote(token, pair, created, at, *, price=1, cooling=False, age_rate=False):
    buys, sells = (7, 3) if age_rate else (10, 4)
    volume = 500 if age_rate else 100
    return TokenSnapshot(token.chain, token.address, price, 10000, 100000, volume, buys, sells,
        observed_at=at, ingested_at=at, provider="dexscreener", raw={"pair": {
            "chainId": token.chain, "pairAddress": pair, "baseToken": {"address": token.address},
            "pairCreatedAt": created, "priceUsd": str(price),
            "priceChange": {"m5": -2 if cooling else 0, "h1": 30 if cooling else 0},
            "volume": {"m5": volume, "h1": 2000 if age_rate else 2100},
            "txns": {"m5": {"buys": buys, "sells": sells},
                     "h1": {"buys": 30 if age_rate else 100, "sells": 10 if age_rate else 100}}}})


def test_additive_registration_preserves_period_and_existing_contracts(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original = store._chain_meme_trader_registration(version)["definition_json"]
    before = store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions").fetchone()[0]
    assert store.register_chain_meme_resource_bound_research() == 6
    assert store.register_chain_meme_resource_bound_research() == 0
    assert store._chain_meme_trader_registration(version)["definition_json"] == original
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions").fetchone()[0] == before
    additions = store.db.execute("SELECT * FROM chain_meme_trader_policy_additions WHERE arm_id LIKE 'resource_%'").fetchall()
    assert len(additions) == 6
    assert len({a["activated_at"] for a in additions}) == 1
    assert len({a["behavior_contract_hash"] for a in additions}) == 6
    store.close()


def test_account_retirement_blocks_queued_buy_without_changing_old_contract(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    store.register_chain_meme_resource_bound_research()
    token = TokenCandidate('solana', 'RetirementFixture', 'Fixture')
    created = int((clock[0]-timedelta(minutes=20)).timestamp()*1000)
    for _ in range(2):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(token, quote(token,'pool',created,clock[0],age_rate=True),recorded_at=clock[0])
    version=store.CHAIN_MEME_TRADER_ACTIVE_VERSION
    original=store._chain_meme_trader_registration(version)['definition_json']
    arm='resource_age_rate_candidate_v1'
    control=store.db.execute("SELECT * FROM chain_meme_trader_entry_decisions WHERE arm_id='resource_age_rate_control_v1'").fetchone()
    store.db.execute("INSERT OR REPLACE INTO chain_meme_trader_entry_decisions(definition_version,arm_id,shadow_cohort_id,token_id,baseline_quote_result_id,decided_at,status,reason) VALUES(?,?,?,?,?,?,'admitted','queued_before_pause')",
        (version,arm,control['shadow_cohort_id'],token.token_id,control['baseline_quote_result_id'],control['decided_at']))
    store.db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)',
        (f'chain-meme-account-convergence/v1:{version}',json.dumps({'activated_at':clock[0].isoformat(),'arms':{arm:{'state':'PAUSED_NEW_ENTRY'}}}),clock[0].isoformat()))
    definition=store._chain_meme_trader_effective_definition(version,original)
    policy=next(p for p in definition['policies'] if p['arm_id']==arm)
    assert not store._chain_meme_trader_policy_active_for_snapshot(policy,{})
    assert store._project_chain_meme_trader_market_entry(version=version,cohort_id=control['shadow_cohort_id'],token_id=token.token_id,
        snapshot_id=control['baseline_quote_result_id'],market_price=1,filled_at=clock[0].isoformat(),reason='queued',definition=definition)==0
    assert store.db.execute('SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id=?',(arm,)).fetchone()[0]==0
    assert store._chain_meme_trader_registration(version)['definition_json']==original
    store.close()


def test_age_filter_keeps_control_and_consumes_rejected_first_opportunity(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    store.register_chain_meme_resource_bound_research()
    token = TokenCandidate("solana", "AgeRateFixture", "Fixture")
    created = int((clock[0] - timedelta(minutes=20)).timestamp() * 1000)
    for i in range(2):
        clock[0] += timedelta(seconds=16)
        count = store.observe_chain_meme_pattern(token, quote(token, "pool", created, clock[0], age_rate=True), recorded_at=clock[0])
        assert count == i
    positions = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'resource_%'").fetchall()
    assert [p["arm_id"] for p in positions] == ["resource_age_rate_control_v1"]
    assert positions[0]["paper_quantity_tokens"] == pytest.approx(5 / 1.04)
    feature = json.loads(store.db.execute("SELECT feature_json FROM chain_meme_trader_v6_entry_evaluations ORDER BY id DESC LIMIT 1").fetchone()[0])
    frozen = feature["resource_bound_opportunities"]["age_rate:pool"]
    assert frozen["candidate_passed"] is False
    assert frozen["decision_at"] < positions[0]["opened_at"]
    # A later stronger aggregate cannot revive the already rejected opportunity.
    for _ in range(2):
        clock[0] += timedelta(seconds=16)
        q = quote(token, "pool", created, clock[0], age_rate=True)
        q.raw["pair"]["volume"]["h1"] = 510
        store.observe_chain_meme_pattern(token, q, recorded_at=clock[0])
    assert store.db.execute("SELECT COUNT(*) FROM chain_meme_trader_positions WHERE arm_id='resource_age_rate_candidate_v1'").fetchone()[0] == 0
    store.close()


def test_cooling_fields_reach_store_and_same_later_fill(tmp_path, monkeypatch):
    store, clock = setup_store(tmp_path, monkeypatch)
    store.register_chain_meme_resource_bound_research()
    token = TokenCandidate("solana", "CoolingFixture", "Fixture")
    created = int((clock[0] - timedelta(hours=2)).timestamp() * 1000)
    for i in range(2):
        clock[0] += timedelta(seconds=16)
        count = store.observe_chain_meme_pattern(token, quote(token, "pool", created, clock[0], cooling=True), recorded_at=clock[0])
        assert count == 2 * i
    positions = store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id LIKE 'resource_cooling_%'").fetchall()
    assert len(positions) == 2 and len({p["source_entry_fill_id"] for p in positions}) == 1
    assert len({p["opened_at"] for p in positions}) == 1
    store.close()


@pytest.mark.parametrize("chain", ["solana", "bsc"])
@pytest.mark.parametrize("retired", [False, True])
def test_profit_structure_masks_only_clock_and_sells_on_later_frame(tmp_path, monkeypatch, chain, retired):
    store, clock = setup_store(tmp_path, monkeypatch)
    store.register_chain_meme_resource_bound_research()
    token = TokenCandidate(chain, "StructureFixture" if chain == "solana" else "0x" + "aB" * 20, "Fixture")
    pair = "pool" if chain == "solana" else "0x" + "cD" * 20
    created = int((clock[0] - timedelta(minutes=2)).timestamp() * 1000)
    for _ in range(2):
        clock[0] += timedelta(seconds=16)
        store.observe_chain_meme_pattern(token, quote(token, pair, created, clock[0]), recorded_at=clock[0])
    arms = ["resource_profit_structure_" + role + "_v1" for role in ("control", "candidate")]
    def position(arm):
        return store.db.execute("SELECT * FROM chain_meme_trader_positions WHERE arm_id=?", (arm,)).fetchone()
    assert position(arms[0])["source_entry_fill_id"] == position(arms[1])["source_entry_fill_id"]
    if retired:
        store.db.execute('INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)',
            (f'chain-meme-account-convergence/v1:{store.CHAIN_MEME_TRADER_ACTIVE_VERSION}',
             json.dumps({'activated_at':clock[0].isoformat(),'arms':{arms[1]:{'state':'RETIRED_DUPLICATE'}}}),clock[0].isoformat()))
    for price in (1.2, 1.15, 1.18, 1.18, 1.18, 1.18, 1.18):
        clock[0] += timedelta(seconds=30)
        store.upsert_chain_meme_trader_market_mark(token, quote(token, pair, created, clock[0], price=price), recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[token.token_id])
    assert position(arms[0])["pending_mark_id"] is not None
    assert position(arms[1])["pending_mark_id"] is None
    for price in (1.18, 1.14, 1.13):
        clock[0] += timedelta(seconds=10)
        store.upsert_chain_meme_trader_market_mark(token, quote(token, pair, created, clock[0], price=price), recorded_at=clock[0])
        store.evaluate_chain_meme_trader_market_marks(now=clock[0], token_ids=[token.token_id])
        if price == 1.14:
            assert position(arms[1])["status"] == "open"
            assert position(arms[1])["pending_mark_id"] is not None
    assert position(arms[0])["status"] == position(arms[1])["status"] == "closed"
    assert position(arms[1])["realized_pnl_usd"] == pytest.approx(5 / 1.04 * 1.13 * .96 - 5)
    store.close()
