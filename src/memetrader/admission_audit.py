"""Bounded, non-trading admission audit; serialization never runs on quote receipt."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

from .models import canonical_token_address


def _epoch(value):
    return value.timestamp() if isinstance(value, datetime) else None


class AdmissionAudit:
    MAX_PENDING = 256
    MAX_PRE = 128
    FLUSH_BATCH = 64
    MAX_BYTES = 256 * 1024 * 1024

    def __init__(self, directory):
        from .admission_shadow import AdmissionShadow
        self.shadow = AdmissionShadow()
        self.path = Path(directory) / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".jsonl")
        self.pending = deque()
        self.receipts = self.dropped = self.written = self.bytes = 0
        self.errors = 0
        self.last_error = ""
        self.reported_drops = 0
        self.last_flush = 0.0
        self.discontinuous = False
        self.flush_task = None

    def capture(self, now, token, snapshot, watch, held, floor):
        self.receipts += 1
        if (self.bytes >= self.MAX_BYTES or len(self.pending) >= self.MAX_PENDING
                or len(watch) > self.MAX_PRE or len(held) > self.MAX_PRE):
            self.dropped += 1
            self.discontinuous = True
            return None
        try:
            raw = snapshot.raw or {}
            pair = raw.get("pair", raw)
            created = pair.get("pairCreatedAt")
            created = float(created) / 1000 if created else None
            received = now.timestamp()
            observed = _epoch(snapshot.observed_at)
            ingested = _epoch(getattr(snapshot, "ingested_at", None))
            price, liquidity = snapshot.price_usd, getattr(snapshot, "liquidity_usd", None)
            pool = canonical_token_address(token.chain, str(pair.get("pairAddress") or ""))
            age = received - created if created is not None else -1
            candidate = dict(token_id=token.token_id, chain=token.chain, pool=pool,
                bucket="early" if age < 900 else "growth" if age < 21600 else "mature",
                created_at=created, observed_at=observed, ingested_at=ingested,
                recorded_at=received, price=price, liquidity=liquidity,
                buys=getattr(snapshot, "buys_5m", None), sells=getattr(snapshot, "sells_5m", None),
                provider=getattr(snapshot, "provider", None),
                quote_asset=canonical_token_address(token.chain, str((pair.get("quoteToken") or {}).get("address") or "")) or None,
                source_snapshot_id=getattr(snapshot, "id", None) or raw.get("snapshot_id"),
                eligible=bool(pool and token.chain in {"bsc", "solana", "robinhood"}
                    and price is not None and math.isfinite(price) and price > 0
                    and liquidity is not None and math.isfinite(liquidity) and liquidity >= floor
                    and age >= 0 and observed is not None and ingested is not None
                    and observed <= ingested <= received and received - observed <= 30))
            pre = [dict(token_id=key, chain=item["token"].chain, pool=item["pair_address"],
                bucket=item["bucket"], expires_at=item["expires_at"].timestamp(),
                held=key in held, observed_at=_epoch(item["quote"].observed_at),
                liquidity=getattr(item["quote"], "liquidity_usd", None)) for key, item in watch.items()]
            event = dict(sequence=self.receipts, received_at=received, candidate=candidate,
                held=sorted(held), actual_pre=pre, decision_eligible=0, affects="none",
                audit_discontinuous=self.discontinuous)
            self.pending.append(event)
            return event
        except (AttributeError, TypeError, ValueError, OverflowError):
            self.dropped += 1
            self.discontinuous = True
            return None

    def _write(self, events, drops):
        rows = []
        if drops:
            rows.append(dict(kind="DROPPED_AUDIT", count=drops, decision_eligible=0, affects="none"))
        for event in events:
            event["challenger"] = self.shadow.process(event)
            rows.append(event)
        payload = "".join(json.dumps(row, ensure_ascii=True, allow_nan=False, default=str) + "\n" for row in rows)
        size = len(payload.encode("utf-8"))
        if self.bytes + size > self.MAX_BYTES:
            self.bytes = self.MAX_BYTES
            raise OSError("audit file byte budget exhausted")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
        self.bytes += size
        return len(events)

    async def flush(self):
        if self.flush_task is not None and not self.flush_task.done():
            return
        if time.monotonic() - self.last_flush < 2:
            return
        self.last_flush = time.monotonic()
        events = [self.pending.popleft() for _ in range(min(len(self.pending), self.FLUSH_BATCH))]
        drops = self.dropped - self.reported_drops
        if not events and not drops:
            return
        # One bounded worker only; slow research disk I/O must not hold up the
        # existing passive-cohort drain or turn it into another background queue.
        self.flush_task = asyncio.create_task(self._flush_events(events, drops))

    async def _flush_events(self, events, drops):
        try:
            self.written += await asyncio.to_thread(self._write, events, drops)
            self.reported_drops += drops
        except Exception as exc:
            # A failed research sink cannot block cohort projection or held exits.
            self.dropped += len(events)
            self.errors += 1
            self.discontinuous = True
            self.last_error = type(exc).__name__ + ": " + str(exc)[:160]

    def status(self):
        return dict(decision_eligible=0, affects="none", receipts=self.receipts,
            written=self.written, pending=len(self.pending), dropped_audit=self.dropped,
            status="DROPPED_AUDIT" if self.dropped else "OBSERVING",
            audit_discontinuous=self.discontinuous, errors=self.errors,
            last_error=self.last_error, bytes=self.bytes, path=str(self.path))
