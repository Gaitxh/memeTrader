"""Append the ALPHA149 strategy arms to the CURRENT forward epoch.

This mirrors `Store.append_chain_meme_trader_policy`
(src/memetrader/store.py) exactly -- same validation, same defaults, same
behavior-contract hash, same activation frontiers -- but uses its own sqlite
connection so the live runtime is not disturbed by constructing a Store over a
38 GB database.

Nothing existing is modified: the only write is one INSERT per new arm into
`chain_meme_trader_policy_additions` (append-only; the table forbids UPDATE and
DELETE by trigger). Arms that already exist are skipped, so the script is
idempotent.

Usage:
    python scripts/register_alpha149.py                 # preview (read-only)
    python scripts/register_alpha149.py --apply         # append the arms
"""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/research/alpha149'
TEMPLATE_ARM = 'dex_hot_impulse_v1'
LEDGER_TABLES = ('chain_meme_trader_positions', 'chain_meme_trader_trades',
                 'chain_meme_trader_fills', 'chain_meme_trader_entry_decisions')


def ledger_digest(c):
    digest = {}
    for table in LEDGER_TABLES:
        rows = c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        if table == 'chain_meme_trader_entry_decisions':
            value = c.execute(f'SELECT SUM(status=\'admitted\') FROM "{table}"').fetchone()[0]
        elif table == 'chain_meme_trader_fills':
            value = rows
        else:
            value = c.execute(f'SELECT ROUND(SUM(realized_pnl_usd),6) FROM "{table}"').fetchone()[0]
        digest[table] = {'rows': rows, 'value': value}
    return digest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    from memetrader import alpha149
    from memetrader.store import Store

    cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    assert not (cfg.get('live') or {}).get('enabled'), 'Live must stay locked'
    db = Path(cfg['database'])
    db = db if db.is_absolute() else ROOT / db
    OUT.mkdir(parents=True, exist_ok=True)

    c = sqlite3.connect(db.as_uri() + ('?mode=rw' if args.apply else '?mode=ro'),
                        uri=True, timeout=5)
    c.row_factory = sqlite3.Row
    c.execute('BEGIN IMMEDIATE' if args.apply else 'BEGIN')

    version = c.execute(
        "SELECT definition_version FROM chain_meme_trader_v6_activations "
        "WHERE entry_execution_enabled=1 ORDER BY activated_at DESC,rowid DESC LIMIT 1"
    ).fetchone()[0]
    raw = c.execute('SELECT definition_json FROM chain_meme_trader_registrations '
                    'WHERE definition_version=?', (version,)).fetchone()
    assert raw is not None, 'current epoch has no registration'
    definition = Store.chain_meme_trader_effective_definition_from_connection(c, version, raw[0])
    existing = {str(p.get('arm_id')) for p in definition['policies']}
    existing_canonical = {str(p.get('canonical_id')) for p in definition['policies']}
    max_stage = max((int(p.get('stage') or 0) for p in definition['policies']), default=0)

    template_row = c.execute(
        'SELECT policy_json FROM chain_meme_trader_policy_additions '
        'WHERE definition_version=? AND arm_id=?', (version, TEMPLATE_ARM)).fetchone()
    assert template_row is not None, f'template arm {TEMPLATE_ARM} missing'
    template = json.loads(template_row[0])
    candidates = alpha149.policies(template)

    snapshot_frontier = int(c.execute('SELECT COALESCE(MAX(id),0) FROM token_snapshots').fetchone()[0])
    evaluation_frontier = int(c.execute(
        'SELECT COALESCE(MAX(id),0) FROM chain_meme_trader_v6_entry_evaluations '
        'WHERE definition_version=?', (version,)).fetchone()[0])
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    before = ledger_digest(c)
    additions = c.execute('SELECT COUNT(*) FROM chain_meme_trader_policy_additions '
                          'WHERE definition_version=?', (version,)).fetchone()[0]
    appended, skipped = [], []
    stage = max_stage
    for policy in candidates:
        arm = str(policy['arm_id'])
        canonical = str(policy['canonical_id'])
        if arm in existing:
            skipped.append(arm)
            continue
        assert canonical not in existing_canonical, f'canonical id already exists: {canonical}'
        candidate = dict(policy)
        stage += 1
        candidate.setdefault('stage', stage)
        candidate.setdefault('forward_enabled', True)
        candidate.setdefault('fidelity_status', 'ADDITIVE_FORWARD')
        candidate.setdefault('no_historical_backfill', True)
        behavior = Store.chain_meme_trader_behavior_hash(candidate, definition_version=version)
        candidate['behavior_contract_hash'] = behavior
        if args.apply:
            c.execute(
                'INSERT INTO chain_meme_trader_policy_additions('
                'definition_version,arm_id,canonical_id,registered_at,activated_at,'
                'activation_snapshot_id,activation_evaluation_id,behavior_contract_hash,'
                'policy_json) VALUES(?,?,?,?,?,?,?,?,?)',
                (version, arm, canonical, now, now, snapshot_frontier,
                 evaluation_frontier, behavior, json.dumps(candidate, ensure_ascii=False)))
        appended.append({'arm_id': arm, 'canonical_id': canonical, 'stage': stage,
                         'notional_usd': candidate.get('notional_usd'),
                         'max_hold_minutes': candidate.get('max_hold_minutes'),
                         'behavior_contract_hash': behavior,
                         'trajectory_engine': candidate.get('trajectory_engine')})
    after = ledger_digest(c)
    c.commit()

    result = {
        'applied': args.apply, 'definition_version': version, 'cutoff': now,
        'source_head': Store.CHAIN_MEME_TRADER_ACTIVE_VERSION,
        'policy_additions_before': additions,
        'policy_additions_after': c.execute(
            'SELECT COUNT(*) FROM chain_meme_trader_policy_additions WHERE definition_version=?',
            (version,)).fetchone()[0],
        'appended_count': len(appended), 'skipped_existing': skipped,
        'appended': appended,
        'activation_snapshot_frontier': snapshot_frontier,
        'activation_evaluation_frontier': evaluation_frontier,
        'ledger_before': before, 'ledger_after': after,
        'ledger_unchanged': before == after,
    }
    assert before == after, 'ledger changed during a policy-only append'
    name = 'registration_applied.json' if args.apply else 'registration_preview.json'
    (OUT / name).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: result[k] for k in
                      ('applied', 'definition_version', 'policy_additions_before',
                       'policy_additions_after', 'appended_count', 'ledger_unchanged')},
                     ensure_ascii=False))
    for row in appended:
        print('  +', row['arm_id'], row['notional_usd'], row['max_hold_minutes'],
              row['trajectory_engine'])
    if skipped:
        print('  skipped (already present):', skipped)


if __name__ == '__main__':
    main()
