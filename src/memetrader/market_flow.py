"""Bounded pure PumpSwap flow from actual SPL transfers and covered event windows.

All windows are (start, end] in block time. Local observed_at and recorded_at
(ingested_at alias) must be known by decision_at. Diagnostic values in an
incomplete frame are not decision eligible. No network or historical backfill.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from itertools import islice
from math import isfinite
from statistics import median
from typing import Any, Iterable, Mapping

MAX_TRADES_PER_WINDOW = 128
IDENTITY_FIELDS = ("pool_address", "base_mint", "quote_mint")
TRADE_FIELDS = (*IDENTITY_FIELDS, "signature", "instruction_path", "side",
                "signer_address", "block_time", "observed_at", "recorded_at",
                "ingested_at", "base_amount_raw", "quote_amount_raw",
                "amount_complete", "amount_source", "slot")


def _time(value):
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value) if isfinite(value) else None
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def _stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z") if value is not None else None


def _receipt(item, decision):
    observed = _time(item.get("observed_at"))
    recorded = _time(item.get("recorded_at", item.get("ingested_at")))
    return (decision is not None and observed is not None and recorded is not None
            and observed <= recorded <= decision)


def _uint(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    if isinstance(value, str) and (not value.isascii() or not value.isdigit()):
        return None
    number = int(value)
    return number if 0 <= number <= 2**64 - 1 else None


def _breadth(values):
    squares = sum(value * value for value in values)
    return sum(values) ** 2 / squares if squares else None


def build_market_frame(
    trades: Iterable[Mapping[str, Any]], *, window_start=None, window_end=None,
    previous_buyers=(), creator_address=None, dust_quote_raw=None, resolver=None,
    scan=None, decision_at=None, quote_conversion=None,
):
    """Aggregate one window; missing identity, receipt or coverage fails closed.

    Resolver: status='verified', exact pool/base/quote, base_decimals and
    quote_decimals, observed_at/recorded_at. Scan: complete=True,
    coverage_complete=True, coverage_start/end, observed_at/recorded_at;
    truncated=True or a TRUNCATED status invalidates it. Trade: explicit
    signer/BUY|SELL, signature/path, block_time, local receipts, raw SPL integer
    base/quote amounts, amount_complete=True, amount_source='parsed_spl_transfer'.
    dust_quote_raw explicitly freezes a native raw quote-unit threshold.
    Optional quote_conversion: quote_mint, usd_per_quote, observed_at,
    recorded_at and max_age_seconds. No implied stablecoin parity or fake USD.
    """
    scan, resolver = scan or {}, resolver or {}
    start, end, decision = map(_time, (window_start, window_end, decision_at))
    reasons = set()
    bounds_ok = start is not None and end is not None and decision is not None and start < end <= decision
    if not bounds_ok:
        reasons.add("invalid_or_future_window")
    decimals = [resolver.get(field) for field in ("base_decimals", "quote_decimals")]
    identity_ok = (resolver.get("status") == "verified"
                   and all(isinstance(resolver.get(field), str) and resolver[field] for field in IDENTITY_FIELDS)
                   and all(type(value) is int and 0 <= value <= 18 for value in decimals)
                   and _receipt(resolver, decision))
    if not identity_ok:
        reasons.add("unverified_identity_decimals_or_time")
    cover_start, cover_end = _time(scan.get("coverage_start")), _time(scan.get("coverage_end"))
    scan_complete = (bounds_ok and scan.get("complete") is True
                     and scan.get("coverage_complete") is True
                     and scan.get("truncated") is not True
                     and "TRUNCATED" not in str(scan.get("status", "")).upper()
                     and cover_start is not None and cover_end is not None
                     and cover_start <= start < end <= cover_end <= decision
                     and _receipt(scan, decision)
                     and cover_end <= _time(scan.get("observed_at")))
    if not scan_complete:
        reasons.add("incomplete_scan_coverage_or_time")
    dust_limit = _uint(dust_quote_raw) if dust_quote_raw is not None else None
    if dust_quote_raw is not None and dust_limit is None:
        reasons.add("invalid_dust_threshold")
    rows = list(islice(trades, MAX_TRADES_PER_WINDOW + 1))
    if len(rows) > MAX_TRADES_PER_WINDOW:
        reasons.add("trade_limit_exceeded")
        rows = rows[:MAX_TRADES_PER_WINDOW]
    unique, conflicts = {}, set()
    invalid_count, duplicate_count = 0, 0
    future = decision is not None and any(
        (value := _time(item.get(field))) is not None and value > decision
        for item in [scan, resolver, *rows] if isinstance(item, Mapping)
        for field in ("observed_at", "recorded_at", "ingested_at", "block_time"))
    for row in rows:
        if (not isinstance(row, Mapping) or not isinstance(row.get("signature"), str)
                or not row["signature"] or not isinstance(row.get("instruction_path"), str)
                or not row["instruction_path"]):
            invalid_count += 1
            continue
        key = (row["signature"], row["instruction_path"])
        # RPC duplicates can have different receipt times, but not evidence.
        fields = [field for field in TRADE_FIELDS if field not in {"observed_at", "recorded_at", "ingested_at"}]
        if key in unique:
            duplicate_count += 1
            if any(row.get(field) != unique[key].get(field) for field in fields) or not _receipt(row, decision):
                conflicts.add(key)
            continue
        unique[key] = row
    eligible = []
    for key, row in unique.items():
        block = _time(row.get("block_time"))
        base, quote = _uint(row.get("base_amount_raw")), _uint(row.get("quote_amount_raw"))
        valid = (key not in conflicts and bounds_ok and identity_ok
                 and all(row.get(field) == resolver[field] for field in IDENTITY_FIELDS)
                 and row.get("amount_complete") is True
                 and row.get("amount_source") == "parsed_spl_transfer"
                 and row.get("side") in {"BUY", "SELL"}
                 and isinstance(row.get("signer_address"), str) and bool(row["signer_address"])
                 and base is not None and base > 0 and quote is not None and quote > 0
                 and block is not None and start < block <= end
                 and _receipt(row, decision) and block <= _time(row.get("observed_at")))
        if not valid:
            invalid_count += 1
            continue
        clean = {field: row[field] for field in TRADE_FIELDS if field in row}
        clean.update(base_amount_raw=base, quote_amount_raw=quote)
        eligible.append(clean)
    if invalid_count:
        reasons.add("invalid_trade_evidence")

    buyers, signature_rows = defaultdict(int), defaultdict(list)
    buys, sells, base_buys, base_sells = [], [], [], []
    previous = set(previous_buyers)
    creator_sell = 0 if creator_address else None
    dust_buy = 0 if dust_limit is not None else None
    for row in eligible:
        who, quote, base = row["signer_address"], row["quote_amount_raw"], row["base_amount_raw"]
        signature_rows[row["signature"]].append(row)
        if row["side"] == "BUY":
            buyers[who] += quote
            buys.append(quote)
            base_buys.append(base)
            if dust_limit is not None and quote <= dust_limit:
                dust_buy += quote
        else:
            sells.append(quote)
            base_sells.append(base)
            if creator_address and who == creator_address:
                creator_sell += quote
    atomic_groups = [{"signature": signature,
                      "instruction_paths": sorted(row["instruction_path"] for row in group),
                      "signer_addresses": sorted({row["signer_address"] for row in group})}
                     for signature, group in sorted(signature_rows.items()) if len(group) > 1]
    # Collapse linked buyer wallets only for actually observed atomic swaps.
    parent = {who: who for who in buyers}
    def find(who):
        while parent[who] != who:
            who = parent[who]
        return who
    for group in atomic_groups:
        wallets = [who for who in group["signer_addresses"] if who in buyers]
        for who in wallets[1:]:
            parent[find(who)] = find(wallets[0])
    adjusted = defaultdict(int)
    for who, amount in buyers.items():
        adjusted[find(who)] += amount
    total_buy, total_sell = sum(buys), sum(sells)
    ranked = sorted(buyers.values(), reverse=True)
    out = {"window_start": _stamp(start), "window_end": _stamp(end), "decision_at": _stamp(decision),
           "observed_at": scan.get("observed_at"), "recorded_at": scan.get("recorded_at", scan.get("ingested_at")),
           "complete": not reasons, "scan_complete": bool(scan_complete), "reasons": sorted(reasons),
           "future_data_rejected": future, "invalid_count": invalid_count, "duplicate_count": duplicate_count,
           "trade_count": len(eligible), "amount_sample_count": len(eligible),
           "buy_count": len(buys), "sell_count": len(sells), "unique_buyers": len(buyers),
           "buyer_addresses": sorted(buyers), "effective_breadth": _breadth(ranked),
           "top1_notional_share": ranked[0] / total_buy if total_buy else None,
           "top3_notional_share": sum(ranked[:3]) / total_buy if total_buy else None,
           "buy_quote_notional_raw": total_buy, "sell_quote_notional_raw": total_sell,
           "net_quote_flow_raw": total_buy - total_sell, "gross_quote_flow_raw": total_buy + total_sell,
           "buy_base_amount_raw": sum(base_buys), "sell_base_amount_raw": sum(base_sells),
           "median_trade_quote_raw": median(buys + sells) if eligible else None,
           "new_buyer_notional_raw": sum(value for who, value in buyers.items() if who not in previous),
           "repeat_buyer_notional_raw": sum(value for who, value in buyers.items() if who in previous),
           "dust_buy_quote_notional_raw": dust_buy, "dust_threshold_quote_raw": dust_limit,
           "creator_sell_quote_notional_raw": creator_sell,
           "creator_sell_notional_share": creator_sell / total_sell if creator_sell is not None and total_sell else None,
           "bundle_status": "unknown", "atomic_coordination_groups": atomic_groups,
           "atomic_coordination_signatures": [group["signature"] for group in atomic_groups],
           "atomic_adjusted_effective_breadth": _breadth(list(adjusted.values())),
           "identity_unit": "signer_address_not_human", "trades": eligible,
           "resolver": {key: resolver[key] for key in (*IDENTITY_FIELDS, "status", "base_decimals",
               "quote_decimals", "observed_at", "recorded_at", "ingested_at", "resolved_slot") if key in resolver},
           "scan": {key: scan[key] for key in ("complete", "coverage_complete", "coverage_start",
               "coverage_end", "truncated", "status", "started_at", "completed_at", "observed_at",
               "recorded_at", "ingested_at", "decoder", "frontier") if key in scan}}
    rate = None
    if identity_ok and isinstance(quote_conversion, Mapping) and _receipt(quote_conversion, decision):
        observed = _time(quote_conversion.get("observed_at"))
        try:
            candidate = float(quote_conversion["usd_per_quote"])
            max_age = float(quote_conversion["max_age_seconds"])
            if (quote_conversion.get("quote_mint") == resolver["quote_mint"]
                    and isfinite(candidate) and candidate > 0 and isfinite(max_age)
                    and 0 <= decision - observed <= max_age):
                rate = candidate
        except (KeyError, TypeError, ValueError):
            pass
    out["quote_conversion"] = ({key: quote_conversion[key] for key in ("quote_mint", "usd_per_quote",
        "observed_at", "recorded_at", "ingested_at", "max_age_seconds", "source") if key in quote_conversion}
        if quote_conversion else None)
    out["usd_conversion_complete"] = rate is not None
    for key, raw in list(out.items()):
        if key.endswith("_raw") and key != "dust_threshold_quote_raw":
            field = key[:-4]
            decimal = decimals[0] if "base_amount" in field else decimals[1]
            units = raw / 10**decimal if identity_ok and raw is not None else None
            out[field] = units
            if "base_amount" not in field:
                out[field + "_usd"] = units * rate if units is not None and rate is not None else None
    out["capital_velocity_quote_per_second"] = (total_buy + total_sell) / 10**decimals[1] / (end - start) if identity_ok and bounds_ok else None
    out["capital_velocity_usd_per_second"] = out["capital_velocity_quote_per_second"] * rate if rate is not None and bounds_ok else None
    out["repeat_buyer_notional_share"] = out["repeat_buyer_notional_raw"] / total_buy if total_buy else None
    out["new_buyer_notional_share"] = out["new_buyer_notional_raw"] / total_buy if total_buy else None
    return out


def aggregate_market_frames(windows: Iterable[Mapping[str, Any]], *, creator_address=None,
                            dust_quote_raw=None, resolver=None, decision_at=None,
                            quote_conversion=None):
    """Require exactly two adjacent complete windows, at most 128 trades each.

    New/repeat is relative to the immediately previous complete window, never
    lifetime history. Receipt times can be later than event windows, but must
    precede the current decision. Raw provenance and diagnostic reasons remain.
    """
    supplied = list(islice(windows, 3))
    built, previous = [], ()
    for window in supplied[:2]:
        frame = build_market_frame(window.get("trades", ()), window_start=window.get("window_start"),
            window_end=window.get("window_end"), previous_buyers=previous,
            creator_address=creator_address, dust_quote_raw=dust_quote_raw, resolver=resolver,
            scan=window.get("scan"), decision_at=decision_at, quote_conversion=quote_conversion)
        built.append(frame)
        previous = frame["buyer_addresses"] if frame["complete"] else ()
    adjacent = (len(built) == 2 and _time(built[0]["window_end"]) is not None
                and _time(built[0]["window_end"]) == _time(built[1]["window_start"]))
    nonoverlap = (len(built) == 2 and _time(built[0]["window_end"]) is not None
                  and _time(built[1]["window_start"]) is not None
                  and _time(built[0]["window_end"]) <= _time(built[1]["window_start"]))
    keys = [(row["signature"], row["instruction_path"]) for frame in built for row in frame["trades"]]
    cross_window_duplicates = len(keys) != len(set(keys))
    complete = (len(supplied) == 2 and adjacent and not cross_window_duplicates
                and all(frame["complete"] for frame in built))
    return {"complete": complete, "window_count": len(supplied), "nonoverlap": nonoverlap,
            "adjacent": adjacent, "cross_window_duplicates": cross_window_duplicates, "windows": built,
            "trades": [row for frame in built for row in frame["trades"]],
            "new_repeat_scope": "previous_complete_window", "bundle_status": "unknown"}
