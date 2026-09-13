"""Bounded held-only Flap migration proof; never creates market/accounting data."""
from __future__ import annotations

import asyncio, json, re, sqlite3, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

from .flap_successor import KEY, PORTAL

RPC = "https://bsc-dataseed.bnbchain.org"
DOCS = "https://docs.flap.sh/flap/developers/inspect-a-token"
GET_TOKEN_V6 = "0xdbde08f0"
STATE_KEY = "held-flap-recovery/v1"
RETRY_SECONDS = 300


def address(value):
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{40}", value):
        raise ValueError("invalid EVM address")
    return value.lower()


def decode_state(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"0x[0-9a-fA-F]{960}", raw):
        raise ValueError("expected exact static TokenStateV6 ABI (15 words)")
    words = [raw[i:i+64] for i in range(2, len(raw), 64)]
    if int(words[0], 16) != 4 or int(words[13][:-40], 16) != 0:
        raise ValueError("official Portal does not confirm canonical DEX migration")
    successor = address("0x" + words[13][-40:])
    if int(successor, 16) == 0:
        raise ValueError("missing successor pool")
    return successor


def _batch(client, calls):
    response = client.post(RPC, json=[dict(jsonrpc="2.0", id=i, method=m, params=p) for i, (m, p) in enumerate(calls)])
    response.raise_for_status(); payload = response.json()
    if not isinstance(payload, list) or len(payload) != len(calls): raise ValueError("invalid RPC batch")
    by_id = {r.get("id"): r for r in payload}
    if set(by_id) != set(range(len(calls))) or any("result" not in r or "error" in r for r in payload): raise ValueError("RPC error/incomplete response")
    return [by_id[i]["result"] for i in range(len(calls))]


def prove(token, original, proxy):
    """One public fixed-block RPC proof. Called only off the runtime main thread."""
    with httpx.Client(proxy=proxy, trust_env=False, timeout=10) as client:
        chain, tip = _batch(client, [("eth_chainId", []), ("eth_blockNumber", [])])
        if chain != "0x38": raise ValueError("wrong chain")
        block = hex(int(tip, 16) - 20)
        def call(to, data): return ("eth_call", [{"to": to, "data": data}, block])
        header, state, old0, old1 = _batch(client, [("eth_getBlockByNumber", [block, False]), call(PORTAL, GET_TOKEN_V6 + token[4:].removeprefix("0x").rjust(64, "0")), call(original, "0x0dfe1681"), call(original, "0xd21220a7")])
        successor = decode_state(state)
        if successor == original: raise ValueError("no pool migration")
        new0, new1, again = _batch(client, [call(successor, "0x0dfe1681"), call(successor, "0xd21220a7"), ("eth_getBlockByNumber", [block, False])])
        def tokens(a, b):
            if any(not isinstance(x, str) or not re.fullmatch(r"0x0{24}[0-9a-fA-F]{40}", x) for x in (a, b)): raise ValueError("invalid pool-token ABI")
            return {address("0x" + x[-40:]) for x in (a, b)}
        old, new = tokens(old0, old1), tokens(new0, new1)
        if token[4:] not in old or old != new or len(old) != 2 or header["number"] != block or header["hash"] != again["hash"]: raise ValueError("pool identity/block mismatch")
        ingested = datetime.now(timezone.utc).isoformat()
        observed = datetime.fromtimestamp(int(header["timestamp"], 16), timezone.utc).isoformat()
        if not 0 <= (datetime.fromisoformat(ingested)-datetime.fromisoformat(observed)).total_seconds() <= 120: raise ValueError("stale/future RPC block")
        return dict(kind="OFFICIAL_MIGRATION_SUCCESSOR", portal=PORTAL, chain_id=56, status=4, token_id=token, original_pool=original, successor_pool=successor, block_number=block, block_hash=header["hash"], observed_at=observed, ingested_at=ingested, rpc_response=state, rpc=RPC, documentation=DOCS, original_tokens=sorted(old), successor_tokens=sorted(new), header=header)


def candidates(path: Path, limit=50):
    """Read-only, bounded original-pool groups; healthy marks never get a probe."""
    con = sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro", uri=True, timeout=.2)
    try:
        deadline=time.monotonic()+.3
        con.set_progress_handler(lambda: int(time.monotonic()>deadline), 1_000)
        cutoff=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
        rows = con.execute("""SELECT p.token_id,lower(json_extract(s.raw_json,'$.pair.pairAddress')) original_pool
          FROM chain_meme_trader_positions p JOIN token_snapshots s ON s.id=p.entry_snapshot_id
          LEFT JOIN kv k ON k.key=?||p.token_id||':'||lower(json_extract(s.raw_json,'$.pair.pairAddress'))
          LEFT JOIN chain_meme_trader_pool_marks m ON m.token_id=p.token_id AND m.pair_address=lower(json_extract(s.raw_json,'$.pair.pairAddress'))
          WHERE p.status='open' AND p.token_id LIKE 'bsc:0x%' AND json_extract(s.raw_json,'$.pair.chainId')='bsc'
            AND json_extract(s.raw_json,'$.pair.dexId')='flapsh' AND k.key IS NULL
            AND (m.token_id IS NULL OR m.liquidity_usd IS NULL OR m.observed_at < ?)
          GROUP BY p.token_id,original_pool LIMIT ?""", (KEY, cutoff, int(limit))).fetchall()
        return [(str(t), address(str(p))) for t,p in rows if p]
    except sqlite3.OperationalError as exc:
        if 'interrupted' in str(exc).lower(): return []
        raise
    finally: con.close()


def _binding(store, token, original):
    rows = store.db.execute("""SELECT s.raw_json FROM chain_meme_trader_positions p JOIN token_snapshots s ON s.id=p.entry_snapshot_id
      WHERE p.status='open' AND p.token_id=?""", (token,)).fetchall()
    for (raw,) in rows:
        pair=json.loads(raw).get('pair',{})
        if str(pair.get('pairAddress','')).lower()==original and pair.get('chainId')=='bsc' and pair.get('dexId')=='flapsh' and str(pair.get('baseToken',{}).get('address','')).lower()==token[4:]: return True
    return False


async def recover_one(runtime):
    """At most one retry-guarded candidate; no network awaits while touching Store."""
    if runtime.config.get('mode') != 'paper' or runtime.config.get('live',{}).get('enabled'): return {'status':'disabled'}
    found = await asyncio.to_thread(candidates, runtime.store.path, 50)
    now=time.time(); state=runtime.store.get_kv(STATE_KEY,{}) or {}; attempts=state.get('pools',{}) if isinstance(state,dict) else {}
    # Oldest attempted candidate first; choosing the first eligible token
    # repeatedly would starve later pools once the 300s cooldown expires.
    def last_attempt(item):
        return float((attempts.get(item[0]+':'+item[1],{}) or {}).get('at',0))
    candidate=min((item for item in found if now-last_attempt(item)>=RETRY_SECONDS),
                  key=last_attempt, default=None)
    if not candidate: return {'status':'none'}
    token,original=candidate; key=token+':'+original
    try:
        proof=await asyncio.to_thread(prove, token, original, runtime.http.proxy_url)
    except Exception as exc:
        attempts[key]={'at':now,'status':'failed','error':type(exc).__name__}; runtime.store.set_kv(STATE_KEY,{'pools':dict(list(attempts.items())[-50:])}); return {'status':'failed'}
    if not _binding(runtime.store,token,original): return {'status':'binding_changed'}
    link_key=KEY+key; prior=runtime.store.db.execute('SELECT value_json FROM kv WHERE key=?',(link_key,)).fetchone()
    if prior:
        if json.loads(prior[0]).get('successor_pool')!=proof['successor_pool']: return {'status':'conflict'}
        return {'status':'existing'}
    proof['recorded_at']=datetime.now(timezone.utc).isoformat(); runtime.store.set_kv(link_key,proof)
    attempts[key]={'at':now,'status':'linked'}; runtime.store.set_kv(STATE_KEY,{'pools':dict(list(attempts.items())[-50:])})
    return {'status':'linked','token':token}
