import json
import sqlite3

from scripts.supervise_metrics import continuity_health, execution_integrity, stability


def database():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE system_error_cases(
          area TEXT,component TEXT,error_type TEXT,message_safe TEXT,
          occurrence_count INTEGER,first_seen_at TEXT,last_seen_at TEXT,status TEXT);
        CREATE TABLE source_health(source TEXT,last_ok_at TEXT,last_error_at TEXT,last_error TEXT);
        CREATE TABLE token_detail_hydration(
          token_id TEXT,status TEXT,next_attempt_at TEXT,attempts INTEGER,followup_until TEXT);
        CREATE TABLE chain_meme_trader_entry_decisions(
          id INTEGER PRIMARY KEY,definition_version TEXT,arm_id TEXT,shadow_cohort_id INTEGER,
          token_id TEXT,decided_at TEXT,status TEXT);
        CREATE TABLE chain_meme_trader_entry_participant_outcomes(
          definition_version TEXT,shadow_cohort_id INTEGER,arm_id TEXT);
        CREATE TABLE chain_meme_trader_positions(
          definition_version TEXT,shadow_cohort_id INTEGER,arm_id TEXT,token_id TEXT,
          source_entry_fill_id INTEGER,opened_at TEXT);
        CREATE TABLE chain_meme_pattern_evidence(
          definition_version TEXT,token_id TEXT,kind TEXT,source_key TEXT,
          recorded_at TEXT,payload_json TEXT);
        CREATE TABLE chain_meme_trader_v6_entry_fills(
          id INTEGER PRIMARY KEY,definition_version TEXT,entry_cohort_id INTEGER,
          execution_attempt_id INTEGER,token_id TEXT,filled_at TEXT);
        CREATE TABLE chain_meme_trader_market_marks(observed_at TEXT);
        CREATE TABLE chain_meme_trader_pool_marks(observed_at TEXT);
    """)
    return con


def test_stability_ignores_fixed_cases_and_parses_iso_timestamps():
    con = database()
    con.execute(
        "INSERT INTO system_error_cases VALUES(?,?,?,?,?,?,datetime('now'),'fixed')",
        ("runtime", "recovered", "Timeout", "safe", 3, "2026-01-01T00:00:00Z"),
    )
    con.execute(
        "INSERT INTO system_error_cases VALUES(?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'),'new')",
        ("runtime", "active", "Timeout", "safe", 1, "2026-01-01T00:00:00Z"),
    )
    con.execute(
        "INSERT INTO system_error_cases VALUES(?,?,?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now','-1 minute'),'new')",
        ("runtime", "recovered-new", "Timeout", "safe", 1, "2026-01-01T00:00:00Z"),
    )
    con.execute(
        "INSERT INTO source_health VALUES('recovered-new',strftime('%Y-%m-%dT%H:%M:%fZ','now'),"
        "strftime('%Y-%m-%dT%H:%M:%fZ','now','-1 minute'),'')"
    )
    out = stability(con, 1)
    assert [row["component"] for row in out["active_error_cases"]] == ["active"]
    assert {row["component"] for row in out["unresolved_errors"]} == {
        "active", "recovered-new",
    }


def test_execution_integrity_exposes_unaccounted_matches_and_paper_boundary():
    con = database()
    con.execute(
        "INSERT INTO chain_meme_trader_entry_decisions VALUES(1,'v','arm-a',7,'bsc:t',"
        "datetime('now','-10 minute'),'admitted')"
    )
    con.execute(
        "INSERT INTO chain_meme_trader_entry_decisions VALUES(2,'v','arm-b',8,'bsc:u',"
        "datetime('now','-10 minute'),'admitted')"
    )
    con.execute(
        "INSERT INTO chain_meme_pattern_evidence VALUES('v','bsc:u','preentry_obvious_scam_v1',"
        "'8:SKIP_DEX_PROXY_CONTINUITY',datetime('now'),?)",
        (json.dumps({"safety_status": "SKIP_DEX_PROXY_CONTINUITY"}),),
    )
    con.execute(
        "INSERT INTO chain_meme_trader_v6_entry_fills VALUES(3,'v',8,-8,'bsc:u',datetime('now'))"
    )
    con.execute(
        "INSERT INTO chain_meme_trader_positions VALUES('v',8,'arm-b','bsc:u',3,datetime('now'))"
    )
    out = execution_integrity(con, "v", 30)
    assert out["admitted"]["admitted"] == 2
    assert out["admitted"]["unaccounted_matured"] == 1
    assert out["bad_position_fill_links"] == 0
    assert out["fill_modes"] == [{"mode": "dex_mark_synthetic_paper", "n": 1}]
    assert "not_live_quote" in out["paper_boundary"]


def test_continuity_health_uses_real_timestamp_age():
    con = database()
    con.execute(
        "INSERT INTO token_detail_hydration VALUES('bsc:t','hydrated',"
        "datetime('now','-2 minute'),1,datetime('now','+1 hour'))"
    )
    con.execute("INSERT INTO chain_meme_trader_market_marks VALUES(datetime('now','-3 minute'))")
    con.execute("INSERT INTO chain_meme_trader_pool_marks VALUES(datetime('now'))")
    out = continuity_health(con)
    assert out["due_followups"]["due"] == 1
    assert out["due_followups"]["oldest_late_s"] >= 119
    assert out["current_mark_age"]["chain_meme_trader_market_marks"]["stale_120s"] == 1
    assert out["current_mark_age"]["chain_meme_trader_pool_marks"]["stale_30s"] == 0
