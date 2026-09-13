"""Reproduce the 2026-09-13 user-supplied right-tail opportunity audit.

This is read-only with respect to trading state.  It distinguishes discovery,
market observations, strategy admission, safety, and Paper fills; the report is
an ex-post diagnostic and never becomes an address allow-list.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
ADDRESSES = [
    "88t4EdAjiuUDzHujJnK5nywitQzYQWEJq2ouUgRGpump",
    "EUTipzFepgT9614RaCQaKcqL2NnJFDmvpTcZTrXYpump",
    "0xceebf25b318201f1f949be2fabbfcee231737139",
    "0xd25efceb9d690e2a75a8b75e52a7c63cb9a214e0",
    "3RTC33FgYgtbhEzXdRgNb2oaVuGPTSyUMkwWPJLx7NBX",
    "0xe27501d787d647cc82a5b4a7eafd5750386f1b77",
    "CNWxmoBSQZo2Sgp5KSAK5m9FwSqDbXQRP4CNMuoe78Gm",
    "3nqHijNUExsnjNBb15WJsJ2xisyMVGN6FK4aUgZk1Rwj",
    "0x3df3644bcf4ce0d993e18c86c3080e53bfea06f1",
    "0x4cb7d9274c659af8c582d79f994f9573f3f07777",
    "7tFbGa9wt4Q4yxNAdaDcTKahv4WPrJtXh6ty7gjWyKx3",
    "0x462dff4be800c77a61e69dc2ea6010e4237f674d",
    "0x4b112e1ed0c0cb332d2b39e5dae3bba882f67777",
    "0xb8cf4ad387cfd607c66a207cfffc46498aacd9d6",
    "5t7fCeQEXcAVAXvBN52fx8u3XY3tWRzqs5AgW3qRpump",
]


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def rows(connection: sqlite3.Connection, sql: str, args=()) -> list[sqlite3.Row]:
    return connection.execute(sql, args).fetchall()


def dex_lookup(address: str) -> list[dict]:
    url = "https://api.dexscreener.com/latest/dex/search?q=" + urllib.parse.quote(address)
    request = urllib.request.Request(url, headers={"User-Agent": "memeTrader-righttail-audit/152"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.load(response)
    except Exception as exc:  # evidence records the provider failure, never guesses
        return [{"status": "error", "error": type(exc).__name__}]
    hits = []
    for pair in payload.get("pairs") or []:
        base = pair.get("baseToken") or {}
        if str(base.get("address") or "").casefold() != address.casefold():
            continue
        hits.append({
            "status": "found", "chain": pair.get("chainId"),
            "dex": pair.get("dexId"), "pair": pair.get("pairAddress"),
            "symbol": base.get("symbol"), "price_usd": pair.get("priceUsd"),
            "liquidity_usd": (pair.get("liquidity") or {}).get("usd"),
        })
    return hits or [{"status": "not_found"}]


def audit_token(connection: sqlite3.Connection, address: str) -> dict:
    token_rows = rows(
        connection,
        "SELECT * FROM tokens WHERE address=? OR lower(address)=lower(?) ORDER BY last_seen_at DESC",
        (address, address),
    )
    if not token_rows:
        return {"address": address, "local_status": "not_found"}
    token = token_rows[0]
    token_id = str(token["token_id"])
    snaps = rows(
        connection,
        "SELECT id,observed_at,recorded_at,provider,price_usd,liquidity_usd "
        "FROM token_snapshots WHERE token_id=? ORDER BY observed_at,id",
        (token_id,),
    )
    valid = [r for r in snaps if r["price_usd"] is not None and float(r["price_usd"]) > 0]
    gaps = [
        (parse(b["observed_at"]) - parse(a["observed_at"])).total_seconds()
        for a, b in zip(snaps, snaps[1:])
    ]
    evaluation = Counter()
    evaluation_rows = rows(
        connection,
        "SELECT status,reason,evaluated_at FROM chain_meme_trader_v6_entry_evaluations "
        "WHERE token_id=? ORDER BY evaluated_at,id",
        (token_id,),
    )
    first_evaluation = None
    for row in evaluation_rows:
        if row["reason"] not in {"pattern_observation", "cohort_observation"}:
            evaluation[f"{row['status']}:{row['reason']}"] += 1
            if first_evaluation is None:
                first_evaluation = {
                    "status": row["status"], "reason": row["reason"],
                    "evaluated_at": row["evaluated_at"],
                }
    decisions = rows(
        connection,
        "SELECT status,reason,COUNT(*) AS n FROM chain_meme_trader_entry_decisions "
        "WHERE token_id=? GROUP BY status,reason",
        (token_id,),
    )
    positions = connection.execute(
        "SELECT COUNT(*) AS n,COUNT(DISTINCT arm_id) AS arms FROM "
        "chain_meme_trader_positions WHERE token_id=?", (token_id,),
    ).fetchone()
    safety = Counter()
    for row in rows(
        connection,
        "SELECT json_extract(payload_json,'$.safety_status') AS status,COUNT(*) AS n "
        "FROM chain_meme_pattern_evidence WHERE token_id=? "
        "AND kind='preentry_obvious_scam_v1' GROUP BY 1",
        (token_id,),
    ):
        safety[str(row["status"])] += int(row["n"])
    admitted = sum(int(r["n"]) for r in decisions if r["status"] == "admitted")
    if positions["n"]:
        blocker = "paper_position_created"
    elif admitted and safety.get("EXPIRED_SECURITY_OR_NEXT_FRAME"):
        blocker = "admitted_then_security_or_next_frame_expired"
    elif admitted:
        blocker = "admitted_but_no_paper_position"
    elif first_evaluation:
        blocker = f"{first_evaluation['status']}:{first_evaluation['reason']}"
    else:
        blocker = "discovered_but_not_enrolled_for_entry_evaluation"
    first_price = float(valid[0]["price_usd"]) if valid else None
    max_price = max((float(r["price_usd"]) for r in valid), default=None)
    return {
        "address": address, "local_status": "found", "token_id": token_id,
        "chain": token["chain"], "name": token["name"], "symbol": token["symbol"],
        "source": token["source"], "first_seen_at": token["first_seen_at"],
        "last_seen_at": token["last_seen_at"], "snapshot_count": len(snaps),
        "distinct_observation_times": len({r["observed_at"] for r in snaps}),
        "first_price_at": valid[0]["observed_at"] if valid else None,
        "first_price_usd": first_price, "max_observed_price_usd": max_price,
        "max_observed_multiple": (max_price / first_price if first_price and max_price else None),
        "max_adjacent_snapshot_gap_seconds": max(gaps, default=None),
        "evaluation_reasons": dict(evaluation),
        "first_entry_evaluation": first_evaluation,
        "dominant_evaluation_reason": evaluation.most_common(1)[0] if evaluation else None,
        "entry_decisions": [dict(r) for r in decisions],
        "position_count": int(positions["n"]), "position_arms": int(positions["arms"]),
        "safety_statuses": dict(safety), "first_blocker": blocker,
    }


def main() -> None:
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    database = Path(config["database"])
    if not database.is_absolute():
        database = ROOT / database
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    audited = [audit_token(connection, address) for address in ADDRESSES]
    connection.close()
    for item in audited:
        if item["local_status"] == "not_found":
            item["dexscreener_live_lookup"] = dex_lookup(item["address"])
    output = ROOT / "data" / "research" / "righttail152"
    output.mkdir(parents=True, exist_ok=True)
    result = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "database": str(database), "address_count": len(ADDRESSES),
        "scope": "ex_post_diagnostic_only_not_strategy_allowlist",
        "tokens": audited,
    }
    (output / "user_examples_diagnostic.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    lines = [
        "# 用户右尾样本全链路诊断 152", "",
        "该报告是事后诊断，不是地址白名单，也不证明首次可见时可安全成交。", "",
        "| 地址 | 本地链 | 快照/时点 | 最大相邻空档 | 记录内最高倍数 | 首个断点 | Paper仓位 |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for item in audited:
        short = item["address"][:10] + "…"
        gap = item.get("max_adjacent_snapshot_gap_seconds")
        multiple = item.get("max_observed_multiple")
        live_hits = [
            hit for hit in item.get("dexscreener_live_lookup", [])
            if hit.get("status") == "found"
        ]
        if item["local_status"] == "not_found" and live_hits:
            chains = ",".join(sorted({str(hit.get("chain") or "unknown") for hit in live_hits}))
            pairs = ",".join(str(hit.get("pair") or "") for hit in live_hits[:2])
            lines.append(
                f"| `{short}` | 本地缺失；DexScreener={chains} | 0/0 | — | — | "
                f"local_not_found_provider_pair={pairs} | 0 |"
            )
            continue
        lines.append(
            f"| `{short}` | {item.get('chain','—')} | "
            f"{item.get('snapshot_count',0)}/{item.get('distinct_observation_times',0)} | "
            f"{gap / 60:.1f}m | {multiple:.2f}x | {item.get('first_blocker','not_found')} | "
            f"{item.get('position_count',0)} |" if gap is not None and multiple is not None else
            f"| `{short}` | {item.get('chain','—')} | 0/0 | — | — | not_found | 0 |"
        )
    (output / "user_examples_diagnostic.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "found": sum(x["local_status"] == "found" for x in audited),
        "missing": sum(x["local_status"] == "not_found" for x in audited),
        "positions": sum(x.get("position_count", 0) for x in audited),
        "output": str(output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
