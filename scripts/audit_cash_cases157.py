"""Read-only cash-veto reconciliation for the supplied casebook, never a reset.

The lightweight path deliberately refuses adjusted or changing funding periods.
Those require a different as-of correction replay, not a raw-ledger shortcut.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import time

from audit_goal_cases156 import stamp

ROOT = Path(__file__).resolve().parents[1]


def check_writeoff_evidence(entry_pool, mark, writeoff_at):
    evidence = json.loads(mark['trigger_evidence_json']).get('terminal_dust_pool') or {}
    pool = lambda value: value.lower() if value and value.startswith('0x') else value
    same_pool = bool(entry_pool and pool(entry_pool) == pool(mark['market_pair_address'])
                     == pool(evidence.get('pair_address')))
    liquidity = evidence.get('liquidity_usd')
    observed, recorded, settled = stamp(evidence.get('observed_at')), stamp(evidence.get('recorded_at')), stamp(writeoff_at)
    causal = all(t is not None for t in (observed, recorded, settled)) and observed <= recorded <= settled
    return dict(same_original_pool=same_pool, causal=causal,
        age_at_settlement_seconds=settled-observed if causal else None,
        known_below_1000=isinstance(liquidity, (int, float)) and math.isfinite(liquidity) and 0 <= liquidity < 1000,
        evidence=evidence)


def cash_at(trades, decision_at, starting_cash):
    cutoff = stamp(decision_at)
    if cutoff is None:
        raise ValueError('invalid decision time')
    usable = []
    for trade in trades:
        created, recorded = stamp(trade['created_at']), stamp(trade['recorded_at'])
        amount = trade['net_cash_flow_usd']
        if created is None or recorded is None or not math.isfinite(amount):
            raise ValueError('incomplete trade cash/time provenance')
        if max(created, recorded) <= cutoff:
            usable.append(trade)
    pnl_available = all(t.get('realized_pnl_usd') is not None
                        and math.isfinite(t['realized_pnl_usd'])
                        for t in usable if t['side'] != 'BUY')
    return dict(cash=starting_cash + math.fsum(t['net_cash_flow_usd'] for t in usable),
        buy_debits=-math.fsum(t['net_cash_flow_usd'] for t in usable if t['side'] == 'BUY'),
        exit_receipts=math.fsum(t['net_cash_flow_usd'] for t in usable if t['side'] != 'BUY'),
        last_available_trade_id=max((t['id'] for t in usable), default=None),
        pnl_available=pnl_available,
        realized_pnl=math.fsum(t.get('realized_pnl_usd') or 0 for t in usable) if pnl_available else None,
        unrecovered_basis_from_ledger=math.fsum(
            (t.get('realized_pnl_usd') or 0) - t['net_cash_flow_usd'] for t in usable) if pnl_available else None,
        trade_count=len(usable), sides=dict(Counter(t['side'] for t in usable)))


def audit(con, casebook, *, seconds=15, row_limit=5000):
    deadline = time.monotonic() + seconds
    con.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    version = casebook['definition_version']
    guards = {}
    for table in ('chain_meme_trader_capital_credits', 'chain_meme_trader_position_voids',
                  'chain_meme_trader_accounting_contaminations',
                  'chain_meme_trader_accounting_contamination_resolutions',
                  'chain_meme_trader_market_fill_corrections',
                  'chain_meme_trader_paper_funding_activations',
                  'chain_meme_trader_fixed_funding_restorations'):
        guards[table] = con.execute(f'SELECT COUNT(*) FROM {table} WHERE definition_version=?',
                                   (version,)).fetchone()[0]
    if any(guards.values()):
        raise ValueError('adjusted/changing period: requires full as-of adjustment replay')
    definition = json.loads(con.execute('SELECT definition_json FROM '
        'chain_meme_trader_v6_registrations WHERE definition_version=?', (version,)).fetchone()[0])
    starting_cash = float(definition['starting_cash_usd_each_arm'])
    notional = float(definition['policy_notional_usd'])
    if starting_cash != 1000 or notional != 20:
        raise ValueError('outside verified uniform 1000/20 funding contract')
    settings = [json.loads(row[0]) for row in con.execute(
        "SELECT value_json FROM kv WHERE key LIKE 'chain-paper-execution:activation:%'")]
    if len(settings) != 1 or settings[0]['definition_fields']['additional_fee_usd_each_fill'] != 0:
        raise ValueError('changing execution fees require explicit activation replay')
    selected = []
    for case in casebook['cases']:
        for match in case['matches']:
            for opportunity in match.get('opportunities', []):
                for decision in opportunity['arm_decisions']:
                    if decision['reason'] == 'entry_cash_below_order_size':
                        selected.append(dict(decision, token_id=match['token']['token_id'],
                            cohort_id=opportunity['cohort']['id']))
    if not selected:
        raise ValueError('no recorded cash-veto decisions in the input casebook')
    first_at = min(stamp(d['decided_at']) for d in selected)
    if stamp(settings[0]['activated_at']) > first_at:
        raise ValueError('fee activation does not cover earliest audited decision')
    histories, arms = {}, sorted({d['arm_id'] for d in selected})
    for arm in arms:
        rows = [dict(r) for r in con.execute('SELECT id,shadow_cohort_id,side,net_cash_flow_usd,realized_pnl_usd,created_at,recorded_at '
            'FROM chain_meme_trader_trades WHERE definition_version=? AND arm_id=? '
            'ORDER BY created_at,id LIMIT ?', (version, arm, row_limit+1))]
        if len(rows) > row_limit:
            raise ValueError('trade history exceeds bounded budget: do not interpret truncated cash')
        histories[arm] = rows
    results = []
    for decision in selected:
        # Re-fetch the immutable decision by PK; the casebook is an input index,
        # not authority to invent a production rejection.
        current = con.execute('SELECT * FROM chain_meme_trader_entry_decisions WHERE id=?',
                              (decision['id'],)).fetchone()
        if current is None or current['definition_version'] != version or any(
            current[key] != decision[key] for key in ('arm_id', 'token_id', 'reason', 'decided_at')):
            raise ValueError('casebook decision does not match current immutable ledger')
        ledger = cash_at(histories[decision['arm_id']], decision['decided_at'], starting_cash)
        results.append(dict(decision, **ledger, required_cash=notional,
            classification=('cash_below_required_at_recorded_decision' if ledger['cash']+1e-9 < notional
                            else 'needs_transaction_frontier_investigation')))
    # Diagnose the largest observed cash shortfall, not a claimed random sample.
    worst = min(results, key=lambda d: (d['cash'], d['id']))
    writeoffs = []
    for trade in histories[worst['arm_id']]:
        if trade['side'] != 'WRITEOFF' or stamp(trade['recorded_at']) > stamp(worst['decided_at']):
            continue
        position = con.execute("SELECT p.token_id,p.entry_snapshot_id,s.liquidity_usd,"
            "json_extract(s.raw_json,'$.pair.pairAddress') entry_pool FROM chain_meme_trader_positions p "
            "JOIN token_snapshots s ON s.id=p.entry_snapshot_id WHERE p.definition_version=? "
            "AND p.arm_id=? AND p.shadow_cohort_id=?", (version, worst['arm_id'], trade['shadow_cohort_id'])).fetchone()
        mark = con.execute("SELECT id,market_pair_address,trigger_evidence_json FROM chain_meme_trader_marks "
            "WHERE definition_version=? AND arm_id=? AND shadow_cohort_id=? AND status='written_off' "
            "ORDER BY id DESC LIMIT 1", (version, worst['arm_id'], trade['shadow_cohort_id'])).fetchone()
        if position is None or mark is None:
            writeoffs.append(dict(trade_id=trade['id'], status='missing_original_evidence'))
        else:
            writeoffs.append(dict(trade_id=trade['id'], mark_id=mark['id'], **dict(position),
                **check_writeoff_evidence(position['entry_pool'], mark, trade['recorded_at'])))
    return dict(cutoff_utc=datetime.now(timezone.utc).isoformat(), version=version,
        source_casebook_cutoff=casebook['cutoff_utc'], adjustment_guards=guards,
        fee_activation=settings[0]['activation_key'], initial_cash=starting_cash, notional=notional,
        token_count=len({d['token_id'] for d in results}), arm_count=len(arms), decision_count=len(results),
        cohort_count=len({d['cohort_id'] for d in results}),
        classifications=dict(Counter(d['classification'] for d in results)), decisions=results,
        worst_cash_arm=worst['arm_id'], writeoff_checks=writeoffs,
        limitations=['Cash is not equity; unavailable position value cannot finance a new buy.',
            'Only recorded cash-veto decisions; not all entry filters or independent token samples.',
            'No original SQL transaction/trade-frontier receipt at decision: disagreements require investigation.',
            'Trade cash is Paper ledger evidence, not proof of economically valid prices or live sellability.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--casebook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
    with sqlite3.connect((ROOT/config['database']).resolve().as_uri()+'?mode=ro', uri=True, timeout=.2) as con:
        con.row_factory = sqlite3.Row
        con.execute('BEGIN')
        result = audit(con, json.loads(args.casebook.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k not in ('decisions', 'writeoff_checks', 'adjustment_guards', 'limitations')}))
