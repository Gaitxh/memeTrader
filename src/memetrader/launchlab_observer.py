"""Official LaunchLab identity evidence; no quote conversion or BUY authority."""
import hashlib
import json
import re
from datetime import datetime, timezone


class LaunchLabObserver:
    CHAIN = "solana"
    ERROR_PREFIX = "raydium_launchlab"
    URL = "https://launch-mint-v1.raydium.io/get/list?sort=new"
    PROGRAM = "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"

    def __init__(self, http):
        self.http = http
        self.activation_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        self.seen = set()

    async def observe(self):
        try:
            response = await self.http.client.get(self.URL, timeout=3)
            response.raise_for_status()
            received = datetime.now(timezone.utc)
            payload = response.json()
            rows = payload.get("data", {}).get("rows")
            if payload.get("success") is not True or not isinstance(rows, list):
                raise ValueError("launchlab_invalid_envelope")
            events = []
            current = set()
            for row in rows[:100]:
                mint = str(row.get("mint") or "")
                pool = str(row.get("poolId") or "")
                if not all(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", s) for s in (mint, pool)):
                    continue
                current.add(mint)
                created = row.get("createAt")
                if (not isinstance(created, (int, float)) or isinstance(created, bool)
                        or not self.activation_ms <= created <= received.timestamp() * 1000
                        or mint in self.seen):
                    continue
                # Provider curve amounts are not USD or executable market marks.
                key = "launchlab:" + hashlib.sha256((mint + ":" + pool).encode()).hexdigest()
                events.append(dict(token=mint, pool=pool, name=row.get("name"),
                    symbol=row.get("symbol"), source_key=key,
                    evidence_kind="official_native_listing", event="ListingObservation",
                    provider="raydium_launchlab", program=self.PROGRAM, source_url=self.URL,
                    published_at_ms=created, observed_at=received.isoformat(),
                    recorded_at=received.isoformat(), raw=row, finality=False, buy_authority=False))
            self.seen = current  # Latest page only; durable evidence key also deduplicates.
            return dict(status="OK", observed_at=received.isoformat(), events=events,
                        indexed_source="raydium_launch_mint", truncated=len(rows) >= 100)
        except Exception as exc:
            return dict(status="ERROR", error=str(exc), events=[])
