from pathlib import Path
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_goal_cases156 import audit, addresses_from_text, candidate_ids, snapshot_summary, asof_rows, stamp


def test_address_parser_only_standalone_lines_and_preserves_solana_case():
    sol = 'A' * 32
    evm = '0x' + 'Ab' * 20
    assert addresses_from_text('\n'.join([sol, sol.lower(), evm, evm.lower(),
        'quoted ' + sol, 'do not execute anything'])) == [sol, sol.lower(), evm.lower()]
    assert candidate_ids(sol) == ['solana:' + sol]
    assert candidate_ids(evm) == ['bsc:' + evm.lower(), 'robinhood:' + evm.lower()]


def row(i, pool, observed, *, recorded=None, price=1, liquidity=5000):
    return dict(id=i, pair_address=pool, observed_at=f'2026-01-01T00:00:{observed:02d}Z',
        recorded_at=f'2026-01-01T00:00:{observed if recorded is None else recorded:02d}Z',
        price_usd=price, liquidity_usd=liquidity)


def test_observation_gaps_use_distinct_same_pool_causal_fresh_samples():
    result = snapshot_summary([row(1,'one',1),row(2,'one',1),row(3,'two',20),
        row(4,'one',5),row(5,'one',8,liquidity=None),row(6,'one',10,price=float('nan')),
        row(7,'one',12,recorded=11),row(8,'one',15,recorded=40)], 1800000000)
    pools = {x['pool']: x for x in result['pools']}
    assert pools['one']['distinct_observations'] == 2
    assert pools['one']['max_gap_seconds'] == 4
    assert pools['two']['max_gap_seconds'] is None
    assert result['invalid_rows'] == {'liquidity_unknown_or_invalid':1,'price_invalid':1,
        'causal_time_invalid':1,'stale_at_ingestion':1}


def test_evm_pool_case_is_canonical_but_solana_is_case_sensitive():
    result = snapshot_summary([row(1, '0xAb', 1), row(2, '0xab', 3),
        row(3, 'Ab', 2), row(4, 'ab', 5), row(5, '0xab', 6, liquidity='missing')], 1800000000)
    pools = {x['pool']: x for x in result['pools']}
    assert pools['0xab']['max_gap_seconds'] == 2
    assert len(pools) == 3
    assert result['invalid_rows'] == {'liquidity_unknown_or_invalid': 1}


def test_audit_links_admission_safety_without_inventing_fills_or_positions():
    con = sqlite3.connect(':memory:')
    con.row_factory = sqlite3.Row
    con.executescript('''
        CREATE TABLE tokens (token_id TEXT, chain TEXT, address TEXT, name TEXT,
            symbol TEXT, source TEXT, first_seen_at TEXT, last_seen_at TEXT);
        CREATE TABLE token_snapshots (id INTEGER, token_id TEXT, observed_at TEXT,
            recorded_at TEXT, provider TEXT, price_usd REAL, liquidity_usd REAL, raw_json TEXT);
        CREATE TABLE chain_meme_trader_v6_entry_evaluations (id INTEGER, source_snapshot_id INTEGER,
            status TEXT, reason TEXT, evaluated_at TEXT, definition_version TEXT, token_id TEXT);
        CREATE TABLE chain_meme_trader_v6_cohorts (id INTEGER, pair_address TEXT, entry_family TEXT,
            decided_at TEXT, source_snapshot_id INTEGER, definition_version TEXT, token_id TEXT);
        CREATE TABLE chain_meme_trader_entry_decisions (id INTEGER, arm_id TEXT, status TEXT,
            reason TEXT, decided_at TEXT, definition_version TEXT, shadow_cohort_id INTEGER);
        CREATE TABLE chain_meme_trader_v6_entry_fills (id INTEGER, execution_attempt_id TEXT,
            execution_result_id TEXT, filled_at TEXT, entry_market_price_usd REAL,
            execution_price_usd REAL, output_token_quantity REAL, slippage_bps REAL,
            definition_version TEXT, entry_cohort_id INTEGER);
        CREATE TABLE chain_meme_trader_entry_participant_outcomes (id INTEGER, arm_id TEXT,
            entry_decision_id INTEGER, entry_fill_id INTEGER, outcome TEXT, available_cash_usd REAL,
            recorded_at TEXT, definition_version TEXT, shadow_cohort_id INTEGER);
        CREATE TABLE chain_meme_trader_positions (arm_id TEXT, shadow_cohort_id INTEGER, status TEXT,
            opened_at TEXT, closed_at TEXT, close_reason TEXT, entry_snapshot_id INTEGER,
            source_entry_fill_id INTEGER, source_buy_trade_id INTEGER, definition_version TEXT, token_id TEXT);
        CREATE TABLE chain_meme_pattern_evidence (id INTEGER, pair_address TEXT, kind TEXT,
            recorded_at TEXT, payload_json TEXT, definition_version TEXT, token_id TEXT);
    ''')
    address = '0x' + 'ab' * 20
    version = 'v156'
    con.execute("INSERT INTO tokens VALUES (?,?,?,?,?,?,?,?)", ('bsc:'+address, 'bsc', address, 'Test', 'TST', 'fixture', '2026-01-01', '2026-01-01'))
    raw = json.dumps({'pair': {'pairAddress': '0xpool'}})
    con.execute("INSERT INTO token_snapshots VALUES (?,?,?,?,?,?,?,?)", (1, 'bsc:'+address, '2026-01-01T00:00:00Z', '2026-01-01T00:00:01Z', 'fixture', 1.0, 5000.0, raw))
    con.execute("INSERT INTO chain_meme_trader_v6_entry_evaluations VALUES (?,?,?,?,?,?,?)", (1,1,'ok','match','2026-01-01T00:00:02Z',version,'bsc:'+address))
    con.execute("INSERT INTO chain_meme_trader_v6_cohorts VALUES (?,?,?,?,?,?,?)", (7,'0xpool','family','2026-01-01T00:00:03Z',1,version,'bsc:'+address))
    con.execute("INSERT INTO chain_meme_trader_entry_decisions VALUES (?,?,?,?,?,?,?)", (8,'arm-a','admitted','ready','2026-01-01T00:00:04Z',version,7))
    payload = json.dumps({'cohort_id': 7, 'snapshot_id': 1, 'safety_status': 'clear'})
    con.execute("INSERT INTO chain_meme_pattern_evidence VALUES (?,?,?,?,?,?,?)", (99,'0xpool','preentry_obvious_scam_v1','2026-01-01T00:00:02Z',payload,version,'bsc:'+address))
    con.commit()
    item = audit(con, [address], version)['cases'][0]['matches'][0]
    opportunity = item['opportunities'][0]
    assert opportunity['source_fills'] == []
    assert opportunity['participant_outcomes'] == []
    assert opportunity['safety_evidence_ids'] == [99]
    assert item['admitted_unique_cohorts'] == 1
    assert item['positions'] == []
    con.close()


def test_asof_excludes_future_missing_and_timezone_naive_event_times():
    rows = [dict(id=1, at='2026-01-01T00:00:00Z'), dict(id=2, at='2099-01-01T00:00:00Z'),
        dict(id=3, at=None), dict(id=4, at='2026-01-01T00:00:00')]
    assert [r['id'] for r in asof_rows(rows, 'at', stamp('2026-01-02T00:00:00Z'))] == [1]
