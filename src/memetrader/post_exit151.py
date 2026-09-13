"""Fixed-horizon research marks, carried only by existing low-priority Dex batches.

No market marks, strategy features, positions, or orders are updated. Durable exits
reconstruct the bounded watch after restart; this is market-price evidence only.
"""
import asyncio
from collections import Counter
from datetime import timedelta
from math import ceil, isfinite
import sqlite3
import time

from .models import canonical_token_address, iso, parse_time, utcnow


def due_windows(path, now):
    started = time.monotonic()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.1) as c:
        c.row_factory = sqlite3.Row
        c.set_progress_handler(lambda: int(time.monotonic()-started > .3), 1000)
        windows = []
        for minutes in (15, 5):
            end = now-timedelta(minutes=minutes)
            rows = c.execute("SELECT p.token_id,p.closed_at,COALESCE("
                "json_extract(s.raw_json,'$.pair.pairAddress'),v.pair_address) pool "
                "FROM (SELECT token_id,closed_at,entry_snapshot_id,shadow_cohort_id FROM "
                "chain_meme_trader_positions WHERE closed_at>=? AND closed_at<=? "
                "ORDER BY closed_at LIMIT 1000) p LEFT JOIN token_snapshots s ON s.id=p.entry_snapshot_id "
                "LEFT JOIN chain_meme_trader_v6_cohorts v ON v.id=p.shadow_cohort_id AND v.token_id=p.token_id",
                (iso(end-timedelta(seconds=60)), iso(end))).fetchall()
            for row in rows:
                if row['pool']:
                    target = parse_time(row['closed_at'])+timedelta(minutes=minutes)
                    windows.append((row['token_id'], row['pool'], target))
        # Exits are the durable queue; skip evidence already stored before restart.
        result = []
        for token, pool, target in dict.fromkeys(windows):
            chain = token.split(':', 1)[0]
            pool = canonical_token_address(chain, pool)
            exists = c.execute("SELECT 1 FROM chain_meme_trader_market_mark_history WHERE "
                "token_id=? AND recorded_at>=? AND recorded_at<=? AND pair_address=? "
                "AND status='VISIBLE' AND price_usd>0 AND julianday(observed_at)>=julianday(?) "
                "AND julianday(recorded_at)-julianday(observed_at) BETWEEN 0 AND 15.0/86400 LIMIT 1",
                (token, iso(target), iso(target+timedelta(seconds=60)), pool, iso(target))).fetchone()
            if not exists:
                result.append((token, pool, target))
        return sorted(result, key=lambda x: x[2])[:96]


class PostExitObservations:
    def __init__(self):
        self.windows = []
        self.attempted = {}
        self.counts = Counter()

    def reload(self, windows, now):
        self.windows = windows[:96]
        self.attempted = {k: v for k, v in self.attempted.items() if (now-v).total_seconds()<60}
        self.counts['reloads'] += 1

    def extend(self, chain, addresses, now):
        result = list(addresses)
        selected = []
        extras = set()
        known = {canonical_token_address(chain, x) for x in addresses}
        for token, pool, target in self.windows:
            if token.split(':', 1)[0] != chain or not target <= now <= target+timedelta(seconds=60):
                continue
            key = (token, pool, target)
            if key in self.attempted and (now-self.attempted[key]).total_seconds()<10:
                continue
            address = token.split(':', 1)[1]
            if address not in known:
                if not addresses or len(result)%30 == 0 or extras:
                    continue
                result.append(address); known.add(address); extras.add(token)
            selected.append(key)
            self.attempted[key] = now
        assert ceil(len(result)/30) == ceil(len(addresses)/30)
        self.counts['selected_windows'] += len(selected)
        self.counts['extra_addresses'] += len(extras)
        return result, selected, extras

    def response(self, store, quoted, selected, now, factory):
        records, observed = {}, set()
        for token_id, pool, target in selected:
            value = (quoted or {}).get(token_id)
            if value is None:
                self.counts['no_token'] += 1
                continue
            token, snapshot = value
            if token.token_id != token_id:
                continue
            raw = snapshot.raw or {}
            exact = next((p for p in raw.get('pairs', []) or [raw.get('pair', raw)]
                if p.get('chainId') == token.chain
                and canonical_token_address(token.chain, str(p.get('pairAddress') or '')) == pool
                and canonical_token_address(token.chain, str((p.get('baseToken') or {}).get('address') or '')) == token.address), None)
            snap = factory(exact) if exact else None
            if (snap is None or not isfinite(snap.price_usd or 0) or (snap.price_usd or 0)<=0
                    or not target <= snapshot.observed_at <= now <= target+timedelta(seconds=60)
                    or not 0 <= (now-snapshot.observed_at).total_seconds() <= 15):
                self.counts['unusable_or_wrong_pool'] += 1
                continue
            records[(token_id, pool)] = (token_id, token.chain, token.address, pool,
                'post-exit151:dexscreener', snap.price_usd, snap.liquidity_usd,
                snap.volume_5m_usd, snap.buys_5m, snap.sells_5m,
                iso(snapshot.observed_at), iso(now))
            observed.add((token_id, pool, target))
        if records:
            with store._lock, store.db:
                store.db.executemany("INSERT INTO chain_meme_trader_market_mark_history("
                    "token_id,chain,address,pair_address,provider,price_usd,liquidity_usd,"
                    "volume_5m_usd,buys_5m,sells_5m,observed_at,recorded_at,status,failure_kind) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'VISIBLE','')", list(records.values()))
            self.windows = [x for x in self.windows if x not in observed]
            self.counts['observed_windows'] += len(observed)
            self.counts['history_rows'] += len(records)

    def snapshot(self):
        return dict(pending_windows=len(self.windows), counts=dict(self.counts),
            additional_http_batches=0, max_windows=96, max_extra_addresses_per_batch=1,
            scope='market_price_research_only_not_execution_or_strategy_features')


async def run(runtime):
    runtime._post_exit151 = PostExitObservations()
    while not runtime._stop.is_set():
        try:
            await asyncio.wait_for(runtime._stop.wait(), timeout=15)
            return
        except TimeoutError:
            pass
        try:
            now = utcnow()
            windows = await asyncio.to_thread(due_windows, runtime.store.path.resolve(), now)
            runtime._post_exit151.reload(windows, now)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Research cannot stall the trading lanes; bounded reader retries later.
            runtime._post_exit151.counts['reload_errors'] += 1
