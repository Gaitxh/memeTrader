import copy
import json
import sqlite3

import pytest

from memetrader.capital_research import (
    competing_risk_context, load_competing_risk_samples, seal_competing_risk_model,
)


FEATURE = "2026-09-05T12:00:00Z"
ENTRY = "2026-09-05T12:00:01Z"
CLOSE = "2026-09-05T12:01:00Z"
CUTOFF = "2026-09-05T12:02:00Z"
TRAINED = "2026-09-05T12:02:01Z"


@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.executescript("""
        CREATE TABLE chain_meme_trader_v6_cohorts(id,definition_version,token_id,
            source_snapshot_id,episode_no,decided_at,pair_address);
        CREATE TABLE chain_meme_trader_positions(definition_version,arm_id,shadow_cohort_id,
            token_id,opened_at,closed_at,status);
        CREATE TABLE token_snapshots(id,token_id,liquidity_usd,observed_at,ingested_at,recorded_at,raw_json);
        CREATE TABLE chain_meme_trader_trades(id,definition_version,arm_id,shadow_cohort_id,
            token_id,side,net_cash_flow_usd,created_at,recorded_at);
        CREATE TABLE chain_meme_trader_quote_results(id,definition_version,shadow_cohort_id,
            validity_status,quote_terminal_status,requested_at,completed_at,recorded_at);
        CREATE TABLE chain_meme_trader_accounting_contaminations(definition_version,arm_id,shadow_cohort_id,recorded_at);
        CREATE TABLE chain_meme_trader_market_fill_corrections(definition_version,arm_id,shadow_cohort_id,recorded_at);
        CREATE TABLE chain_meme_trader_capital_credits(definition_version,arm_id,shadow_cohort_id,recorded_at);
    """)
    for i in range(1, 22):
        token = f"solana:mint{i}"
        c.execute("INSERT INTO chain_meme_trader_v6_cohorts VALUES(?,?,?,?,?,?,?)", (i,"v",token,i,1,ENTRY,"pool"))
        c.execute("INSERT INTO chain_meme_trader_positions VALUES(?,?,?,?,?,?,?)", ("v","a",i,token,ENTRY,CLOSE,"written_off" if i==21 else "closed"))
        c.execute("INSERT INTO token_snapshots VALUES(?,?,?,?,?,?,?)", (i,token,20000,FEATURE,FEATURE,FEATURE,json.dumps({"pair":{"pairAddress":"pool"}})))
        c.execute("INSERT INTO chain_meme_trader_trades VALUES(?,?,?,?,?,?,?,?,?)", (i*2,"v","a",i,token,"BUY",-20,ENTRY,ENTRY))
        c.execute("INSERT INTO chain_meme_trader_trades VALUES(?,?,?,?,?,?,?,?,?)", (i*2+1,"v","a",i,token,"WRITEOFF" if i==21 else "SELL",0 if i==21 else 25 if i<=15 else 18,CLOSE,CLOSE))
    yield c
    c.close()


def infer(model, **kwargs):
    args = dict(token_id="solana:new", liquidity_usd=20000,
                observed_at=TRAINED, recorded_at=TRAINED, decision_at=TRAINED)
    return competing_risk_context(model, **(args | kwargs))


def test_real_closed_ledger_bins_and_unknown_route(db):
    source = load_competing_risk_samples(db,"v",CUTOFF)
    model = seal_competing_risk_model(source,trained_at=TRAINED)
    r = infer(model)
    assert len(source["samples"]) == 21
    assert r["sample_status"] == "sufficient_sample"
    assert r["p_profit"] == pytest.approx(15/21)
    assert r["p_death"] == pytest.approx(1/21)
    assert r["p_ordinary_loss"] == pytest.approx(5/21)
    assert r["p_no_route"] is None and r["route_coverage"] == 0
    assert infer(model, liquidity_usd=9999)["sample_status"] == "insufficient_sample"
    assert infer(model, token_id="bsc:new")["sample_status"] == "insufficient_sample"


@pytest.mark.parametrize("table", ["chain_meme_trader_accounting_contaminations",
    "chain_meme_trader_market_fill_corrections", "chain_meme_trader_capital_credits"])
def test_engineering_rows_excluded_not_added_to_profit(db, table):
    db.execute(f"INSERT INTO {table} VALUES('v','a',21,?)", (CLOSE,))
    source = load_competing_risk_samples(db,"v",CUTOFF)
    assert len(source["samples"]) == 20
    assert source["excluded"]["engineering_pollution"] == 1


@pytest.mark.parametrize("sql", [
    "UPDATE token_snapshots SET recorded_at='2026-09-05T12:00:02Z' WHERE id=21",
    "UPDATE token_snapshots SET ingested_at=NULL WHERE id=21",
    "UPDATE token_snapshots SET raw_json='{}' WHERE id=21",
    "UPDATE chain_meme_trader_trades SET recorded_at='2026-09-05T12:03:00Z' WHERE id=43",
    "UPDATE chain_meme_trader_positions SET closed_at='2026-09-05T12:03:00Z' WHERE shadow_cohort_id=21",
])
def test_future_missing_identity_excluded(db,sql):
    db.execute(sql)
    assert len(load_competing_risk_samples(db,"v",CUTOFF)["samples"]) == 20


def test_duplicates_and_open_preselected_arm_are_not_extra_successes(db):
    db.execute("INSERT INTO chain_meme_trader_positions SELECT definition_version,'z',shadow_cohort_id,token_id,opened_at,closed_at,status FROM chain_meme_trader_positions")
    assert len(load_competing_risk_samples(db,"v",CUTOFF)["samples"]) == 21
    db.execute("UPDATE chain_meme_trader_positions SET status='open',closed_at=NULL WHERE arm_id='a' AND shadow_cohort_id=21")
    assert len(load_competing_risk_samples(db,"v",CUTOFF)["samples"]) == 20


def test_sealed_model_cannot_relabel_history_and_route_requires_observation(db):
    db.execute("INSERT INTO chain_meme_trader_quote_results VALUES(1,'v',20,'valid','no_route',?,?,?)", (ENTRY,CLOSE,CLOSE))
    model = seal_competing_risk_model(load_competing_risk_samples(db,"v",CUTOFF),trained_at=TRAINED)
    frozen = copy.deepcopy(model)
    assert infer(model)["p_no_route"] == 1 and infer(model)["route_observed_samples"] == 1
    db.execute("UPDATE chain_meme_trader_trades SET net_cash_flow_usd=999 WHERE id=43")
    assert model == frozen
    assert infer(model, decision_at=CUTOFF)["sample_status"] == "noncausal_or_stale_model"
    assert infer(model, decision_at="2026-09-05T12:03:00Z")["sample_status"] == "noncausal_or_stale_model"
    with pytest.raises(ValueError):
        seal_competing_risk_model({"cutoff_at":CUTOFF,"samples":[]},trained_at=ENTRY)


def test_bounds_and_under20_maturity(db):
    source = load_competing_risk_samples(db,"v",CUTOFF,max_cohorts=19,max_samples=19)
    assert source["scanned_cohorts"] == 19
    assert infer(seal_competing_risk_model(source,trained_at=TRAINED))["sample_status"] == "insufficient_sample"
    with pytest.raises(ValueError):
        load_competing_risk_samples(db,"v",CUTOFF,max_cohorts=1025)
