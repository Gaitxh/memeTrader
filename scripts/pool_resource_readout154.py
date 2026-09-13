"""Read-only, bounded release evidence for pool acquisition and held gaps."""
import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


def capture(root, *, with_api=False, skip_due=False):
    config = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
    db = (root / config['database']).resolve()
    con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=3)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    deadline = time.monotonic() + 5
    con.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    def rows(sql, args=()):
        return [dict(row) for row in con.execute(sql, args)]
    out = dict(cutoff_utc=now, mode=config.get('mode'), live_enabled=config.get('live', {}).get('enabled'),
        due=None if skip_due else rows("SELECT chain,status,CASE WHEN followup_until IS NULL THEN 'initial_or_retry' ELSE 'followup' END lane,COUNT(*) n FROM token_detail_hydration WHERE status IN ('pending','no_pair','error','hydrated') AND (next_attempt_at<=? OR (next_attempt_at IS NULL AND followup_until IS NULL AND status IN ('pending','no_pair','error'))) AND (followup_until IS NULL OR followup_until>?) GROUP BY chain,status,lane", (now, now)),
        due_measurement='skipped_operator_latency_budget' if skip_due else 'measured',
        open_pools=rows("""SELECT p.definition_version,p.token_id,
            COALESCE(json_extract(e.raw_json,'$.pair.pairAddress'),c.pair_address) pool,
            COUNT(*) positions,m.status,m.failure_kind,m.observed_at,m.last_success_at,m.last_attempt_at,
            m.price_usd,m.liquidity_usd
            FROM chain_meme_trader_positions p
            LEFT JOIN token_snapshots e ON e.id=p.entry_snapshot_id AND e.token_id=p.token_id
            LEFT JOIN chain_meme_trader_v6_cohorts c ON c.id=p.shadow_cohort_id AND c.definition_version=p.definition_version
            LEFT JOIN chain_meme_trader_pool_marks m ON m.token_id=p.token_id AND m.pair_address=
            CASE WHEN p.token_id LIKE 'solana:%' THEN COALESCE(json_extract(e.raw_json,'$.pair.pairAddress'),c.pair_address)
            ELSE LOWER(COALESCE(json_extract(e.raw_json,'$.pair.pairAddress'),c.pair_address)) END
            WHERE p.status='open' GROUP BY p.definition_version,p.token_id,pool ORDER BY positions DESC LIMIT 100"""),
        source_health=rows("SELECT source,last_ok_at,last_item_at,last_error_at,last_error FROM source_health WHERE source IN ('chain-meme-market-marks','dexscreener:hydration','dexscreener:original_pool','geckoterminal:original_pool','chain-meme-pattern-observer')"),
        frontier=rows("SELECT (SELECT MAX(id) FROM token_snapshots) snapshot_id,(SELECT MAX(id) FROM chain_meme_trader_trades) trade_id"),
        acquisition_state=rows("SELECT key,value_json AS value FROM kv WHERE key IN ('pool-followup-resources:v1','chain-meme-pattern-watch')"))
    con.close()
    for item in out['acquisition_state']:
        item['value'] = json.loads(item['value'])
    if with_api:
        import httpx
        with httpx.Client(trust_env=False, timeout=10) as client:
            live = client.get('http://127.0.0.1:8790/api/live')
            live.raise_for_status()
            performance = client.get('http://127.0.0.1:8790/api/performance')
            performance.raise_for_status()
        data = performance.json()
        timing = data.get('timing', {})
        components = ('held_fetch', 'held_apply_exit', 'chain_meme_market_marks',
                      'chain_meme_account_snapshot', 'chain_meme_token_details')
        manifest = data.get('execution_diagnostics', {}).get('runtime-loaded-manifest', {})
        out['api'] = dict(system=live.json().get('system'), generated_at=data.get('generated_at'),
            loaded={k: v for k, v in manifest.items() if k != 'policy_arm_ids'},
            components={k: timing.get('components', {}).get(k) for k in components},
            activity={k: timing.get('activity', {}).get(k) for k in components},
            http_capacity=timing.get('dex_http_capacity'), held_by_chain=data.get('held_by_chain'))
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--with-api', action='store_true')
    parser.add_argument('--skip-due', action='store_true', help='omit full due-count aggregate during latency incidents')
    args = parser.parse_args()
    result = capture(Path(__file__).resolve().parents[1], with_api=args.with_api, skip_due=args.skip_due)
    body = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body + '\n', encoding='utf-8')
        print(str(args.output))
    else:
        print(body)
