"""Held-only authenticated Flap surface resolution; never changes entry provenance."""
import json
from datetime import datetime

PORTAL = "0xe2ce6ab80874fa9fa2aae65d277dd6b8e65c9de0"
KEY = "official-flap-successor/v1:"

def resolve(connection, token, original, at):
    if not str(token).startswith("bsc:") or not original:
        return None
    row = connection.execute("SELECT value_json FROM kv WHERE key=?", (KEY+token+":"+str(original).lower(),)).fetchone()
    if not row:
        return None
    try:
        link = json.loads(row[0])
        times = [datetime.fromisoformat(str(link[k]).replace("Z", "+00:00")) for k in ("observed_at", "ingested_at", "recorded_at")]
        end = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        successor = link["successor_pool"]
        if successor != successor.lower():
            return None  # receipts require canonical EVM identity
        if (link["portal"] != PORTAL or link["chain_id"] != 56 or link["status"] != 4
                or link["token_id"] != token or link["original_pool"] != str(original).lower()
                or len(successor) != 42 or int(successor,16) == 0 or successor == str(original).lower()
                or not times[0] <= times[1] <= times[2] < end):
            return None
        return link
    except (ValueError, KeyError, TypeError):
        return None

def matches(connection, token, original, candidate, observed_at):
    link = resolve(connection, token, original, observed_at)
    return bool(link and str(candidate).lower() == link["successor_pool"])
