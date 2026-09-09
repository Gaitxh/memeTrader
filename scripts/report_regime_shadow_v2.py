"""On-demand local receipt regime. Read-only, bounded, no trading consumers."""
import argparse
import collections
import json
import math
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path


def stamp(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError, AttributeError):
        return None


def summarize(exposures, snapshots, evidence, cutoff, spans):
    result = {}
    for label, lo, hi in [('current', cutoff-900, cutoff), ('baseline', cutoff-1800, cutoff-900)]:
        groups = collections.defaultdict(lambda: dict(receipts={}, frames={}, stages=collections.defaultdict(set), providers=collections.Counter()))
        for e in exposures:
            t = stamp(e['recorded_at'])
            obs = stamp(e['observed_at'])
            if t is None or obs is None or not obs <= t <= hi or t <= lo:
                continue
            keys = [e['chain']]
            if e['provider'] == 'native-launch':
                keys.append(e['chain']+'/'+e['surface'])
            for key in keys:
                if e['first_local_discovery']:
                    groups[key]['receipts'].setdefault(e['token_id'], t)
        for s in snapshots:
            obs, ing, rec = (stamp(s[k]) for k in ('observed_at','ingested_at','recorded_at'))
            if None in (obs, ing, rec) or not obs <= ing <= rec <= hi or rec <= lo or rec-obs > 15:
                continue
            price, liq = s['price_usd'], s['liquidity_usd']
            if not s['pair'] or price is None or liq is None or not math.isfinite(price) or not math.isfinite(liq) or price <= 0 or liq < 1000:
                continue
            chain = s['token_id'].split(':')[0]
            keys = [chain] + [k for k in list(groups) if '/' in k and s['token_id'] in groups[k]['receipts']]
            for key in keys:
                groups[key]['frames'].setdefault(s['token_id'], s)
                groups[key]['providers'][s['upstream'] or s['provider']] += 1
        for e in evidence:
            obs, rec = stamp(e['observed_at']), stamp(e['recorded_at'])
            if obs is None or rec is None or not obs <= rec <= hi or rec <= lo:
                continue
            stage = json.loads(e['payload_json']).get('stage')
            if stage in ('MIGRATED','CURVE_COMPLETE'):
                for key in ('solana', 'solana/pump-pregrad-watch'):
                    groups[key]['stages'][stage].add(e['token_id'])
        out = {}
        for key, g in groups.items():
            mature = {t:r for t,r in g['receipts'].items() if r <= hi-300}
            delays = []
            for token, receipt in mature.items():
                s = g['frames'].get(token)
                if s and stamp(s['observed_at']) >= receipt:
                    delay = stamp(s['recorded_at'])-receipt
                    if 0 <= delay <= 300:
                        delays.append(delay)
            early = [s for s in g['frames'].values() if s['created'] is not None and 0 <= stamp(s['observed_at'])-s['created']/1000 < 900]
            known = [s for s in early if (s['buys_5m'] is not None and s['sells_5m'] is not None) or s['volume_5m_usd'] is not None]
            active = [s for s in known if (s['buys_5m'] is not None and s['sells_5m'] is not None and s['buys_5m']+s['sells_5m'] >= 3) or (s['volume_5m_usd'] is not None and s['volume_5m_usd'] >= 200)]
            median = lambda xs: statistics.median(xs) if xs else None
            covered = all(v is not None and v <= lo for v in spans.values())
            out[key] = dict(coverage='LOCAL_WINDOW_COMPLETE' if covered else 'UNKNOWN',
                unique_first_local_receipts=len(g['receipts']), mature_300s_receipts=len(mature),
                converted_300s=len(delays), conversion_share=len(delays)/len(mature) if mature and covered else None,
                median_conversion_seconds=median(delays), unique_early_liquid=len(early), unique_early_active=len(active),
                activity_missing=len(early)-len(known), median_early_liquidity=median([s['liquidity_usd'] for s in early]),
                median_turnover=median([s['volume_5m_usd']/s['liquidity_usd'] for s in early if s['volume_5m_usd'] is not None]),
                pregrad_events={k:len(v) for k,v in g['stages'].items()}, provider_frames=dict(g['providers']),
                opportunity_signal_incidence=None, opportunity_status='UNKNOWN_NOT_READ')
        result[label] = out
    for key, current in result['current'].items():
        prior = result['baseline'].get(key, {})
        usable = current['coverage'] == prior.get('coverage') == 'LOCAL_WINDOW_COMPLETE' and prior.get('unique_first_local_receipts',0) >= 20 and current['unique_first_local_receipts'] >= 20
        current['receipt_intensity_ratio'] = current['unique_first_local_receipts']/prior['unique_first_local_receipts'] if usable else None
        current['intensity_status'] = 'LOCAL_RECEIPT_RATIO' if usable else 'UNKNOWN'
    return result


def discovery_tail(db, frontier, prior_start, *, initial=10000, cap=40000):
    """Expand only unread older PK ranges; cap is total ID span, not per query."""
    rows, width, upper = [], min(initial, cap), frontier
    while True:
        lower = max(0, frontier-width)
        batch = [dict(r) for r in db.execute(
            'SELECT e.*,r.provider,r.surface FROM token_discovery_exposures e '
            'JOIN token_discovery_rounds r ON r.id=e.round_id '
            'WHERE e.id>? AND e.id<=? ORDER BY e.id', (lower, upper))]
        rows = batch + rows
        earliest = min((stamp(r['recorded_at']) for r in rows
                        if stamp(r['recorded_at']) is not None), default=None)
        if (earliest is not None and earliest <= prior_start) or lower == 0 or width == cap:
            return rows, width
        upper, width = lower, min(cap, width*2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--database', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    started = time.monotonic()
    cutoff = datetime.now(timezone.utc)
    with sqlite3.connect(Path(args.database).resolve().as_uri()+'?mode=ro', uri=True, timeout=1) as db:
        db.row_factory = sqlite3.Row
        # Each statement and the overall run are bounded; never scan historical tables.
        db.set_progress_handler(lambda: int(time.monotonic()-started > 3), 1000)
        frontiers = {t:db.execute('SELECT MAX(id) FROM '+t).fetchone()[0] or 0 for t in ('token_discovery_exposures','token_snapshots','chain_meme_pattern_evidence')}
        exposures, discovery_span = discovery_tail(db, frontiers['token_discovery_exposures'], cutoff.timestamp()-1800)
        snapshots = [dict(r) for r in db.execute("SELECT token_id,observed_at,ingested_at,recorded_at,price_usd,liquidity_usd,buys_5m,sells_5m,volume_5m_usd,provider,json_extract(raw_json,'$.pair.pairAddress') pair,json_extract(raw_json,'$.pair.pairCreatedAt') created,json_extract(raw_json,'$.upstream_provider') upstream FROM token_snapshots WHERE id>? AND id<=? ORDER BY id", (max(0,frontiers['token_snapshots']-12000),frontiers['token_snapshots']))]
        evidence = [dict(r) for r in db.execute("SELECT token_id,kind,observed_at,recorded_at,CASE WHEN kind='pregrad_watch' THEN payload_json ELSE '{}' END payload_json FROM chain_meme_pattern_evidence WHERE id>? AND id<=? ORDER BY id", (max(0,frontiers['chain_meme_pattern_evidence']-10000),frontiers['chain_meme_pattern_evidence']))]
    spans = {k:min((stamp(r['recorded_at']) for r in rows if stamp(r['recorded_at']) is not None),default=None) for k,rows in [('discovery',exposures),('market',snapshots),('evidence',evidence)]}
    result = dict(schema='local-regime-shadow-v2', cutoff=cutoff.isoformat(), decision_eligible=False, affects='none', outcomes_read=False,
        frontiers=frontiers, discovery_id_span=discovery_span, discovery_hard_cap=40000,
        row_counts=dict(discovery=len(exposures),market=len(snapshots),evidence=len(evidence)), coverage_start=spans,
        windows=summarize(exposures,snapshots,evidence,cutoff.timestamp(),spans),
        limitations=['Local observed supply only; not chain-wide truth.', 'Truncated windows UNKNOWN, never COLD. Pregrad watch-selected.', 'Conversion uses first retained qualifying exact-pool frame; no inferred launch time.', 'No PnL/ATH/outcomes, no trading consumer. Freeze cutoff before future outcome research.'])
    result['elapsed_seconds'] = time.monotonic()-started
    path = Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(path),elapsed_seconds=result['elapsed_seconds'],row_counts=result['row_counts'])))


if __name__ == '__main__':
    try:
        main()
    except sqlite3.OperationalError as exc:
        # A budget-interrupted read must not leave a newly claimed complete state.
        if str(exc) != 'interrupted':
            raise
        print(json.dumps({'status': 'UNKNOWN', 'reason': 'sqlite_3s_budget_exceeded',
                          'report_written': False}))
        raise SystemExit(2)
