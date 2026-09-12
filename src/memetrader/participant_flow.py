"""PARTICIPANT FLOW: read the participant counts the providers already send.

Round-3 measured that `token_snapshots.buyers_5m` is filled 0 times in the newest
20,000 rows while the stored `raw_json` of the very same rows DOES contain
`buyers`/`sellers` (864 occurrences against 2,380 `buys`): the numbers are already
fetched and paid for, they are simply never parsed into a column. This module is the
pure parser for that payload, so "new-participant growth" can stop being a proxy.

Payload shapes handled (all observed in this database's `raw_json`):
* geckoterminal   : data.attributes.transactions.{m5,h1,h24}.{buys,sells,buyers,sellers}
* dexscreener     : pair.txns.{m5,h1,h24}.{buys,sells}   (no buyer counts)
* strategy-observer wrappers: {"raw": {...}} / {"cohort_observer": {...}} / nested pairs[]

Nothing here writes, fetches or decides: it is a parser plus a small amount of
arithmetic. A missing field returns None - never a substituted zero.
"""
from __future__ import annotations

from typing import Any, Mapping

VERSION = "participant-flow/v1"
WINDOWS = ("m5", "h1", "h6", "h24")


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _walk(node: Any, depth: int = 0):
    """Yield every dict inside an arbitrarily nested payload (bounded depth)."""
    if depth > 8:
        return
    if isinstance(node, Mapping):
        yield node
        for value in node.values():
            yield from _walk(value, depth + 1)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item, depth + 1)


def _from_transactions(block: Any) -> dict[str, int | None]:
    """geckoterminal style: one dict per window with buys/sells/buyers/sellers."""
    result: dict[str, int | None] = {}
    if not isinstance(block, Mapping):
        return result
    for window in WINDOWS:
        entry = block.get(window)
        if not isinstance(entry, Mapping):
            continue
        for field in ("buys", "sells", "buyers", "sellers"):
            value = _int(entry.get(field))
            if value is not None:
                result[f"{field}_{window}"] = value
    return result


def _from_txns(block: Any) -> dict[str, int | None]:
    """dexscreener style: txns.m5 = {buys, sells} (no buyer counts)."""
    result: dict[str, int | None] = {}
    if not isinstance(block, Mapping):
        return result
    for window in WINDOWS:
        entry = block.get(window)
        if not isinstance(entry, Mapping):
            continue
        for field in ("buys", "sells", "buyers", "sellers"):
            value = _int(entry.get(field))
            if value is not None:
                result.setdefault(f"{field}_{window}", value)
    return result


def extract(raw: Any) -> dict[str, Any]:
    """Return the participant/transaction counts found anywhere in a raw payload."""
    found: dict[str, int | None] = {}
    shapes: set[str] = set()
    if isinstance(raw, Mapping):
        for node in _walk(raw):
            if "transactions" in node:
                block = _from_transactions(node.get("transactions"))
                if block:
                    found.update(block)
                    shapes.add("geckoterminal_transactions")
            if "txns" in node:
                block = _from_txns(node.get("txns"))
                if block:
                    for key, value in block.items():
                        found.setdefault(key, value)
                    shapes.add("dexscreener_txns")
            # Some wrappers publish the window dicts at the top level.
            if any(window in node for window in ("m5", "h1")):
                block = _from_transactions({w: node.get(w) for w in WINDOWS})
                if block:
                    for key, value in block.items():
                        found.setdefault(key, value)
                    shapes.add("flat_windows")
    buyers = found.get("buyers_m5")
    buys = found.get("buys_m5")
    per_trade = None
    if buyers is not None and buys:
        per_trade = round(buyers / buys, 4)
    return {
        "version": VERSION,
        "buyers_5m": buyers,
        "sellers_5m": found.get("sellers_m5"),
        "buys_5m": buys,
        "sells_5m": found.get("sells_m5"),
        "buyers_h1": found.get("buyers_h1"),
        "sellers_h1": found.get("sellers_h1"),
        "participants_per_trade_5m": per_trade,
        "shapes": sorted(shapes),
        "fields": sorted(found),
    }


def buyers_5m(raw: Any) -> int | None:
    """Convenience accessor for the snapshot writer."""
    return extract(raw)["buyers_5m"]


def net_new_participants_5m(raw: Any) -> int | None:
    """buyers - sellers over 5 minutes; None unless BOTH counts exist."""
    result = extract(raw)
    buyers, sellers = result["buyers_5m"], result["sellers_5m"]
    if buyers is None or sellers is None:
        return None
    return buyers - sellers


def snapshot() -> dict[str, Any]:
    return {"version": VERSION, "windows": list(WINDOWS),
            "fields": ["buyers", "sellers", "buys", "sells"],
            "affects": "observation_only"}
