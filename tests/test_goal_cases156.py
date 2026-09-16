from pathlib import Path
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_goal_cases156 import (audit, addresses_from_text, candidate_ids,
    creation_discovery_timeline, snapshot_summary, asof_rows, stamp, markdown)


def test_address_parser_only_standalone_lines_and_preserves_solana_case():
    sol = 'A' * 32
    evm = '0x' + 'Ab' * 20
    assert addresses_from_text('\n'.join([sol, sol.lower(), evm, evm.lower(),
        'quoted ' + sol, 'do not execute anything'])) == [sol, sol.lower(), evm.lower()]
    assert candidate_ids(sol) == ['solana:' + sol]
    assert candidate_ids(evm) == ['bsc:' + evm.lower(), 'robinhood:' + evm.lower()]


def test_address_parser_accepts_goal_attachment_html_spacing_only():
    sol = 'A' * 32
    evm = '0x' + 'ab' * 20
    assert addresses_from_text(
        f'&#x20;  {sol}\n&nbsp; {evm}\nquoted &#x20; {sol}'
    ) == [sol, evm]


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
    assert result['first_valid_recorded_pool_snapshot']['snapshot_id'] == 1


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
            symbol TEXT, source TEXT, created_at TEXT, first_seen_at TEXT, last_seen_at TEXT);
        CREATE TABLE token_snapshots (id INTEGER, token_id TEXT, observed_at TEXT,
            recorded_at TEXT, provider TEXT, price_usd REAL, liquidity_usd REAL, raw_json TEXT);
        CREATE TABLE token_discovery_rounds (id INTEGER, provider TEXT, surface TEXT,
            mode TEXT, status TEXT, started_at TEXT, completed_at TEXT);
        CREATE TABLE token_discovery_exposures (id INTEGER, round_id INTEGER,
            token_id TEXT, role TEXT, first_local_discovery INTEGER, no_pair INTEGER,
            observed_at TEXT, recorded_at TEXT);
        CREATE TABLE token_launch_facts (id INTEGER, token_id TEXT, launch_provider TEXT,
            launch_surface TEXT, launch_event_type TEXT, source_observed_at TEXT,
            ingested_at TEXT, recorded_at TEXT);
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
            source_entry_fill_id INTEGER, source_buy_trade_id INTEGER, last_fill_id INTEGER,
            stake_usd REAL, realized_pnl_usd REAL, realized_proceeds_usd REAL,
            allocated_cost_usd REAL, definition_version TEXT, token_id TEXT);
        CREATE TABLE chain_meme_pattern_evidence (id INTEGER, pair_address TEXT, kind TEXT,
            recorded_at TEXT, payload_json TEXT, definition_version TEXT, token_id TEXT);
    ''')
    address = '0x' + 'ab' * 20
    version = 'v156'
    con.execute("INSERT INTO tokens VALUES (?,?,?,?,?,?,?,?,?)", ('bsc:'+address, 'bsc', address, 'Test', 'TST', 'fixture', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'))
    con.execute("INSERT INTO token_discovery_rounds VALUES (?,?,?,?,?,?,?)", (1,'fixture','new','poll','completed','2026-01-01T00:00:00Z','2026-01-01T00:00:02Z'))
    con.execute("INSERT INTO token_discovery_exposures VALUES (?,?,?,?,?,?,?,?)", (1,1,'bsc:'+address,'discovery',1,0,'2026-01-01T00:00:00Z','2026-01-01T00:00:01Z'))
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
    assert item['creation_discovery']['first_exposure']['provider'] == 'fixture'
    assert item['creation_discovery']['first_local_discovery_exposure']['id'] == 1
    assert item['discovery_to_valid_pool_quote_seconds'] == 0.0
    rendered = markdown({'cutoff_utc': '2026-01-02T00:00:00Z',
        'remaining_addresses': [], 'limitations': [],
        'cases': [{'address': address, 'matches': [item]}]})
    assert '准入但未成交的逐机会记录' in rendered
    assert '无终局回执' in rendered
    assert '无原始BUY成交' in rendered
    assert '创建与发现时点证据' in rendered
    con.close()


def test_creation_timeline_never_promotes_future_or_unreceived_event():
    cutoff = stamp('2026-01-02T00:00:00Z')
    token = {'created_at': '2026-01-01T00:00:00Z'}
    exposures = [
        {'id': 1, 'observed_at': '2026-01-01T00:00:10Z',
         'recorded_at': '2026-01-01T00:00:12Z', 'first_local_discovery': 1},
        {'id': 2, 'observed_at': '2026-01-03T00:00:00Z',
         'recorded_at': '2026-01-03T00:00:01Z', 'first_local_discovery': 1},
    ]
    launches = [
        {'id': 1, 'source_observed_at': '2026-01-01T00:00:00Z',
         'ingested_at': '2026-01-01T00:00:20Z', 'recorded_at': '2026-01-01T00:00:21Z'},
        {'id': 2, 'source_observed_at': '2026-01-01T00:00:00Z',
         'ingested_at': '2026-01-03T00:00:00Z', 'recorded_at': '2026-01-03T00:00:01Z'},
    ]
    snapshots = [
        {'id': 1, 'pair_address': 'pool', 'provider': 'dex',
         'pair_created_at': 1767225600000, 'observed_at': '2026-01-01T00:00:30Z',
         'recorded_at': '2026-01-01T00:00:31Z'},
        {'id': 2, 'pair_address': 'other', 'provider': 'dex',
         'pair_created_at': 1767398400000, 'observed_at': '2026-01-01T00:00:32Z',
         'recorded_at': '2026-01-01T00:00:33Z'},
    ]
    result = creation_discovery_timeline(token, exposures, launches, snapshots, cutoff)
    assert result['valid_exposure_count'] == 1
    assert result['first_local_discovery_exposure']['id'] == 1
    assert result['valid_launch_fact_count'] == 1
    assert result['first_launch_fact']['recorded_at'] == '2026-01-01T00:00:21Z'
    assert result['first_reported_pair_creation']['pair_address'] == 'pool'


def test_first_valid_pool_keeps_its_own_provider_created_time():
    rows = [
        {**row(1, 'bad', 1, price=None), 'pair_created_at': 1767225500000},
        {**row(2, 'good', 5), 'pair_created_at': 1767225602000},
    ]
    result = snapshot_summary(rows, stamp('2026-01-02T00:00:00Z'))
    first = result['first_valid_recorded_pool_snapshot']
    assert first['pair_address'] == 'good'
    assert first['reported_pair_created_at'] == '2026-01-01T00:00:02+00:00'


def test_asof_excludes_future_missing_and_timezone_naive_event_times():
    rows = [dict(id=1, at='2026-01-01T00:00:00Z'), dict(id=2, at='2099-01-01T00:00:00Z'),
        dict(id=3, at=None), dict(id=4, at='2026-01-01T00:00:00')]
    assert [r['id'] for r in asof_rows(rows, 'at', stamp('2026-01-02T00:00:00Z'))] == [1]


def test_markdown_distinguishes_first_rejection_from_later_admission_and_exit():
    token = {'token_id': 'solana:test', 'first_seen_at': '2026-01-01T00:00:00Z'}
    report = {'cutoff_utc': '2026-01-02T00:00:00Z', 'remaining_addresses': [],
        'limitations': [], 'cases': [{'address': 'test', 'matches': [{
            'token': token, 'sampled_snapshot_count': 2, 'evaluation_sample_count': 2,
            'admitted_unique_cohorts': 1, 'admitted_arm_decisions': 1,
            'filled_unique_cohorts': 1, 'path_status': 'position',
            'first_evaluation': {'evaluated_at': '2026-01-01T00:01:00Z',
                                 'reason': 'entry_pool_liquidity_below_configured_floor'},
            'opportunities': [{'cohort': {'id': 7, 'pair_address': 'pool-a'},
                               'source_fills': [{'id': 1}]}],
            'positions': [{'arm_id': 'arm-a', 'shadow_cohort_id': 7,
                           'source_entry_fill_id': 1, 'stake_usd': 20.0,
                           'realized_pnl_usd': -2.0, 'last_fill_id': 9,
                           'status': 'closed', 'opened_at': '2026-01-01T00:02:00Z',
                           'closed_at': '2026-01-01T00:05:00Z',
                           'close_reason': 'time_exit'}],
            'first_position_at': '2026-01-01T00:02:00Z',
        }]}]}
    rendered = markdown(report)
    assert '首评是该资金期首次被记录的判断' in rendered
    assert 'entry_pool_liquidity_below_configured_floor' in rendered
    assert '1准入机会 / 1原始BUY成交 / 1策略仓位' in rendered
    assert 'time_exit:1' in rendered
    assert '20.0 / -2.0 / 9' in rendered
