from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "pumpportal_live_smoke.json"


async def main() -> int:
    observed = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated_at": observed,
        "purpose": "Live transport smoke test only; not historical decision evidence.",
        "historical_decision_eligible": False,
        "endpoint": "wss://pumpportal.fun/api/data",
        "received": False
    }
    try:
        async with websockets.connect("wss://pumpportal.fun/api/data", ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"method": "subscribeNewToken"}))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=45)
                item = json.loads(raw)
                address = item.get("mint") or item.get("tokenAddress")
                if address:
                    payload["received"] = True
                    payload["message_observed_at"] = datetime.now(timezone.utc).isoformat()
                    payload["sample"] = {
                        "mint": address,
                        "name": item.get("name"),
                        "symbol": item.get("symbol"),
                        "trader_public_key": item.get("traderPublicKey"),
                        "tx_type": item.get("txType")
                    }
                    break
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "received": payload["received"]}, ensure_ascii=False))
    return 0 if payload["received"] else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
