"""Bounded official Four.meme listing/progress discovery; never a market quote."""
import hashlib
import json
import re
from datetime import datetime, timezone

class FourMemeRestObserver:
    CHAIN = "bsc"
    ERROR_PREFIX = "four_meme_rest"
    URL = "https://four.meme/meme-api/v1/public/token/search"

    def __init__(self, http):
        self.http = http
        self.cycle = 0

    async def observe(self):
        kind = ("NEW", "NEW", "PROGRESS")[self.cycle % 3]
        self.cycle += 1
        try:
            response = await self.http.client.post(self.URL,
                json=dict(type=kind, listType="NOR", pageIndex=1, pageSize=30, status="ALL", sort="DESC"),
                headers={"Accept": "application/json"}, timeout=3)
            response.raise_for_status()
            received = datetime.now(timezone.utc).isoformat()
            payload = response.json()
            if payload.get("code") != 0 or not isinstance(payload.get("data"), list):
                raise ValueError("four_meme_rest_invalid_envelope")
            events = []
            for row in payload["data"][:30]:
                address = str(row.get("tokenAddress") or "").lower()
                if (not re.fullmatch(r"0x[0-9a-f]{40}", address) or int(address,16)==0
                        or row.get("networkCode") != 0 or row.get("status") not in ("PUBLISH", "TRADE")):
                    continue
                # Raw amounts have provider-specific quote units, NOT assumed USD.
                identity = [address, row.get("status"), row.get("progress"), row.get("createDate")]
                key = "four-rest:"+hashlib.sha256(json.dumps(identity).encode()).hexdigest()
                events.append(dict(token=address, name=row.get("name"), symbol=row.get("shortName"),
                    source_key=key, evidence_kind="official_native_listing", event="ListingObservation",
                    provider="four.meme", source_url=self.URL, listing_type=kind,
                    published_at_ms=row.get("createDate"), observed_at=received, recorded_at=received,
                    raw=row, finality=False, buy_authority=False))
            return dict(status="OK", observed_at=received, events=events)
        except Exception as exc:
            return dict(status="ERROR", error=str(exc), events=[])
