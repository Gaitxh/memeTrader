"""Fixed-block public Flap proof for an existing held original pool.

Read-only by default; --apply may add only the existing authenticated-successor
KV link. No price, fill, position or historical record is manufactured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from memetrader.flap_successor import KEY
from memetrader.held_flap_recovery import address, decode_state, prove

ROOT = Path(__file__).resolve().parents[1]


def stamp():
    return datetime.now(timezone.utc).isoformat()


def held_binding(con, token, original):
    rows = con.execute("""SELECT p.entry_snapshot_id,s.raw_json
        FROM chain_meme_trader_positions p JOIN token_snapshots s ON s.id=p.entry_snapshot_id
        WHERE p.status='open' AND p.token_id=?""", (token,)).fetchall()
    matches = []
    for row in rows:
        pair = json.loads(row[1]).get("pair", {})
        if str(pair.get("pairAddress", "")).lower() != original:
            continue
        if (pair.get("chainId") != "bsc" or pair.get("dexId") != "flapsh"
                or str(pair.get("baseToken", {}).get("address", "")).lower() != token[4:]):
            raise ValueError("held entry does not authenticate original Flap token/pool")
        matches.append(int(row[0]))
    if not matches:
        raise ValueError("no open Flap position for exact original pool")
    return matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", required=True)
    parser.add_argument("--original-pool", required=True)
    parser.add_argument("--proxy", default="socks5://127.0.0.1:7890")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    token, original = "bsc:"+address(args.token.removeprefix("bsc:")), address(args.original_pool)
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    if config.get("mode") != "paper" or config.get("live", {}).get("enabled"):
        raise ValueError("Paper/Live-disabled config required")
    db = (ROOT / config["database"]).resolve()
    with sqlite3.connect(db.as_uri()+"?mode=ro", uri=True, timeout=.5) as con:
        held = held_binding(con, token, original)
    proof = prove(token, original, args.proxy)
    proof["entry_snapshot_ids"] = sorted(set(held))
    proof["recorded_at"] = stamp()
    archive = ROOT / "data/research/held_flap160" / (proof["recorded_at"].replace(":", "") + ".json")
    archive.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(proof, sort_keys=True, indent=2)
    with archive.open("x", encoding="utf-8") as handle:
        handle.write(body)
    link = {**proof, "evidence_sha256": hashlib.sha256(body.encode()).hexdigest()}
    applied = False
    if args.apply:
        with sqlite3.connect(db.as_uri()+"?mode=rw", uri=True, timeout=.5) as con:
            deadline = time.monotonic()+2
            con.set_progress_handler(lambda: int(time.monotonic()>deadline), 1000)
            con.execute("BEGIN IMMEDIATE")
            held_binding(con, token, original)
            key = KEY+token+":"+original
            prior = con.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
            if prior:
                if json.loads(prior[0])["successor_pool"] != link["successor_pool"]:
                    raise ValueError("conflicting existing successor link")
            else:
                con.execute("INSERT INTO kv(key,value_json,updated_at) VALUES(?,?,?)",
                            (key, json.dumps(link), link["recorded_at"]))
                applied = True
    print(json.dumps(dict(applied=applied, proof=str(archive), held_positions=len(held),
        token=token, original=original, successor=proof["successor_pool"],
        block=proof["block_number"], recorded_at=proof["recorded_at"])))


if __name__ == "__main__":
    main()
