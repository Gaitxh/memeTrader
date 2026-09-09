"""Frozen P0-C feature/hazard research; no production writes or strategy action.

The third strict same-pool frame is the availability boundary.  Every outcome
starts after that frame was recorded, so the result cannot reuse universe71's
earlier second-frame entry labels.  Numeric zero is an observed value; only a
missing/non-numeric field makes a feature frame incomplete.
"""
from __future__ import annotations

import collections
import itertools
import json
import math
import sqlite3
import statistics
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_DIR = ROOT / "data" / "research" / "universe71"
OUT = ROOT / "data" / "research" / "features74"
NORMALIZED = UNIVERSE_DIR / "normalized_identity.sqlite3"
UNIVERSE = UNIVERSE_DIR / "universe.json"
SOURCE = ROOT / "data" / "memetrader_forward_20260830_r6.sqlite3"
FRONTIER = 2_194_123
HORIZON_SECONDS = 3_600
ENDPOINT_TOLERANCE_SECONDS = 120
RAW_CHUNK = 500


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def value_state(value: object) -> str:
    if not finite(value):
        return "missing_or_invalid"
    return "zero" if float(value) == 0 else "nonzero"


def median(values: list[float]) -> float:
    assert values
    return statistics.median(values)


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def output_stats(rows: list[dict]) -> dict:
    """Use the complete feature denominator; UNKNOWN paths remain in it."""
    n = len(rows)
    observed = [r for r in rows if r["future_state"] == "OBSERVED"]
    tails = sum(r["tail100"] is True for r in rows)
    losses = sum(r["loss50"] is True for r in rows)
    endpoint = sum(r["endpoint_observed"] for r in rows)
    return {
        "feature_complete": n,
        "future_observed": len(observed),
        "future_unknown": n - len(observed),
        "future_coverage": rate(len(observed), n),
        "endpoint_observed": endpoint,
        "endpoint_coverage": rate(endpoint, n),
        "tail100": tails,
        "tail100_rate_full_denominator": rate(tails, n),
        "loss50": losses,
        "loss50_hazard_rate_full_denominator": rate(losses, n),
        "tail100_rate_observed_only": rate(tails, len(observed)),
        "loss50_rate_observed_only": rate(losses, len(observed)),
    }


def path_state(raw: object, *keys: str) -> object:
    current = raw
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def raw_audit(rows: list[dict]) -> tuple[dict, dict[int, bool]]:
    """Read only selected episode IDs, never scan production snapshots for this audit."""
    ids = sorted({frame_id for row in rows for frame_id in row["frame_ids"]})
    assert ids and len(ids) <= len(rows) * 3
    source = sqlite3.connect(f"file:{SOURCE.as_posix()}?mode=ro", uri=True)
    source.execute("PRAGMA query_only=ON")
    raw_by_id: dict[int, dict] = {}
    for begin in range(0, len(ids), RAW_CHUNK):
        chunk = ids[begin : begin + RAW_CHUNK]
        assert len(chunk) <= RAW_CHUNK
        marks = ",".join("?" for _ in chunk)
        # Explicit id cap protects the frozen fact boundary even if the source grows.
        query = f"SELECT id, raw_json FROM token_snapshots WHERE id <= ? AND id IN ({marks})"
        for frame_id, raw_json in source.execute(query, [FRONTIER, *chunk]):
            try:
                raw_by_id[frame_id] = json.loads(raw_json or "{}")
            except json.JSONDecodeError:
                raw_by_id[frame_id] = {}
    source.close()
    assert set(raw_by_id).issubset(ids)

    fields = {
        "pair.volume.m5": ("pair", "volume", "m5"),
        "pair.txns.m5.buys": ("pair", "txns", "m5", "buys"),
        "pair.txns.m5.sells": ("pair", "txns", "m5", "sells"),
    }
    counts = {field: collections.Counter() for field in fields}
    by_provider: dict[str, dict[str, collections.Counter]] = {}
    raw_complete_by_id: dict[int, bool] = {}
    for row in rows:
        provider = row["provider"]
        provider_counts = by_provider.setdefault(provider, {field: collections.Counter() for field in fields})
        for frame_id in row["frame_ids"]:
            raw = raw_by_id.get(frame_id, {})
            complete = True
            for field, path in fields.items():
                state = value_state(path_state(raw, *path))
                counts[field][state] += 1
                provider_counts[field][state] += 1
                complete = complete and state != "missing_or_invalid"
            raw_complete_by_id[frame_id] = complete
    return {
        "audited_episodes": len(rows),
        "audited_frame_ids": len(ids),
        "returned_frame_ids": len(raw_by_id),
        "query_chunk_max": RAW_CHUNK,
        "fields": {key: dict(value) for key, value in counts.items()},
        "by_provider": {provider: {key: dict(value) for key, value in value.items()} for provider, value in by_provider.items()},
    }, raw_complete_by_id


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    assert universe["meta"]["complete"] is True
    assert universe["meta"]["source_frontier"] == FRONTIER
    assert universe["meta"]["source_cutoff"] == "2026-09-09T04:55:14.116134+00:00"
    anchor_meta = {
        row["anchor_id"]: row
        for row in universe["rows"]
        if row["original"] and row["day"] in ("2026-09-07", "2026-09-08")
    }
    assert anchor_meta

    normalized = sqlite3.connect(f"file:{NORMALIZED.as_posix()}?mode=ro", uri=True)
    normalized.row_factory = sqlite3.Row
    episodes: list[dict] = []
    excluded = collections.Counter()
    query = "SELECT * FROM frames ORDER BY token,pool,rec,id"
    for (token, pool), group in itertools.groupby(normalized.execute(query), lambda r: (r["token"], r["pool"])):
        frames = list(group)
        anchor = frames[0]
        meta = anchor_meta.get(anchor["id"])
        if meta is None:
            continue
        # normalized_identity already enforces the exact pool, floor and three clocks.
        assert token == meta["token"] and pool == meta["pool"]
        second = next((row for row in frames[1:] if row["obs"] > anchor["rec"]), None)
        if second is None:
            excluded["second_missing"] += 1
            continue
        third = next((row for row in frames if row["rec"] > second["rec"] and row["obs"] > second["rec"]), None)
        if third is None:
            excluded["third_missing"] += 1
            continue
        gap12 = second["rec"] - anchor["rec"]
        gap23 = third["rec"] - second["rec"]
        if gap12 <= 0 or gap23 <= 0:
            excluded["nonpositive_availability_spacing"] += 1
            continue
        # Do not pool different provider aggregate semantics into one feature frame.
        if len({anchor["source"], second["source"], third["source"]}) != 1:
            excluded["provider_changed_in_first3"] += 1
            continue
        need = ("price", "liq", "volume", "buys", "sells")
        if any(not finite(frame[key]) for frame in (anchor, second, third) for key in need):
            excluded["feature_frame_missing_or_invalid"] += 1
            continue
        if min(anchor["price"], second["price"], third["price"], anchor["liq"], second["liq"], third["liq"]) <= 0:
            excluded["feature_frame_nonpositive"] += 1
            continue
        reported_notional = (anchor["volume"] + second["volume"] + third["volume"]) / 3
        trade_count = third["buys"] + third["sells"]
        if reported_notional < 0 or trade_count < 0:
            excluded["feature_denominator_invalid"] += 1
            continue
        displacement = third["price"] / anchor["price"] - 1
        vol_liq = reported_notional / third["liq"]
        path_distance = abs(second["price"] - anchor["price"]) + abs(third["price"] - second["price"])
        features = {
            "displacement_per_reported_notional_proxy": displacement / reported_notional if reported_notional else None,
            "reported_activity_efficiency_proxy": displacement / vol_liq if vol_liq else None,
            "volume_to_liquidity": vol_liq,
            "buy_count_imbalance": ((third["buys"] - third["sells"]) / trade_count) if trade_count else None,
            "liquidity_growth": third["liq"] / anchor["liq"] - 1,
            "liquidity_retention": min(second["liq"], third["liq"]) / anchor["liq"],
            "path_efficiency": abs(third["price"] - anchor["price"]) / path_distance if path_distance else None,
            "second_third_acceleration_per_second": ((third["price"] / second["price"] - 1) / gap23) - ((second["price"] / anchor["price"] - 1) / gap12),
        }
        assert all(value is None or finite(value) for value in features.values())

        future = [row for row in frames if row["obs"] > third["rec"] and row["obs"] <= third["rec"] + HORIZON_SECONDS]
        # The whole list above is after third availability; this is the no-leakage invariant.
        assert all(row["obs"] > third["rec"] for row in future)
        endpoint = next((row for row in frames if third["rec"] + HORIZON_SECONDS <= row["obs"] <= third["rec"] + HORIZON_SECONDS + ENDPOINT_TOLERANCE_SECONDS), None)
        returns = [row["price"] * 0.96 / (third["price"] * 1.04) - 1 for row in future]
        future_state = "OBSERVED" if returns else "UNKNOWN"
        episodes.append({
            "day": meta["day"], "chain": meta["chain"], "provider": anchor["source"],
            "anchor_id": anchor["id"], "frame_ids": [anchor["id"], second["id"], third["id"]],
            "gap12_seconds": gap12, "gap23_seconds": gap23, "features": features,
            "future_state": future_state,
            "endpoint_observed": endpoint is not None,
            "tail100": max(returns) >= 1 if returns else None,
            "loss50": min(returns) <= -0.5 if returns else None,
        })
    normalized.close()
    assert all(row["day"] in ("2026-09-07", "2026-09-08") for row in episodes)
    assert all(len(row["frame_ids"]) == 3 for row in episodes)

    # Audit every candidate first3 ID, then remove raw-dependent diagnostics when
    # the raw provider field is absent/invalid.  Numeric raw zero remains valid.
    raw_result, raw_complete_by_id = raw_audit(episodes)
    raw_dependent = {
        "displacement_per_reported_notional_proxy",
        "reported_activity_efficiency_proxy",
        "volume_to_liquidity",
        "buy_count_imbalance",
    }
    for row in episodes:
        row["raw_aggregate_complete"] = all(raw_complete_by_id.get(frame_id, False) for frame_id in row["frame_ids"])
        if not row["raw_aggregate_complete"]:
            for feature in raw_dependent:
                row["features"][feature] = None

    train = [row for row in episodes if row["day"] == "2026-09-07"]
    holdout = [row for row in episodes if row["day"] == "2026-09-08"]
    assert train and holdout
    medians = {key: median([row["features"][key] for row in train if row["features"][key] is not None]) for key in train[0]["features"]}
    for row in episodes:
        row["bins"] = {key: ("high_or_equal_train_median" if value >= medians[key] else "low_train_median") if value is not None else None for key, value in row["features"].items()}

    broad: dict[str, dict] = {}
    strata: dict[str, dict] = {}
    for day in ("2026-09-07", "2026-09-08"):
        day_rows = [row for row in episodes if row["day"] == day]
        all_complete = [row for row in day_rows if all(value is not None for value in row["features"].values())]
        broad[day] = {
            "first3_complete": output_stats(day_rows),
            "all_diagnostics_complete": output_stats(all_complete),
            "feature_availability": {feature: sum(row["features"][feature] is not None for row in day_rows) for feature in medians},
            "by_feature_bin": {},
        }
        for feature in medians:
            broad[day]["by_feature_bin"][feature] = {
                label: output_stats([row for row in day_rows if row["bins"][feature] == label])
                for label in ("low_train_median", "high_or_equal_train_median")
            }
        for chain, provider in sorted({(row["chain"], row["provider"]) for row in day_rows}):
            subset = [row for row in day_rows if row["chain"] == chain and row["provider"] == provider]
            strata[f"{day}:{chain}:{provider}"] = output_stats(subset)

    result = {
        "schema_version": 1,
        "purpose": "frozen causal feature/hazard research only; no strategy or alpha claim",
        "frozen_input": {
            "normalized_db": str(NORMALIZED.relative_to(ROOT)),
            "universe": str(UNIVERSE.relative_to(ROOT)),
            "frontier": FRONTIER,
            "cutoff": universe["meta"]["source_cutoff"],
            "horizon_seconds_after_third_availability": HORIZON_SECONDS,
            "endpoint_tolerance_seconds": ENDPOINT_TOLERANCE_SECONDS,
        },
        "definition": {
            "first3": "first normalized original-pool frame, then first same-pool frame observed after prior recorded availability, three valid/floor frames",
            "provider_rule": "all first3 provider labels equal",
            "future": "strictly observed after third recorded availability; missing path is UNKNOWN",
            "cost_proxy": "4% buy and 4% sell price costs for labels only",
            "reported_notional": "mean of overlapping reported 5m volume snapshots; not swap-level notional",
        },
        "excluded": dict(excluded),
        "episodes": {"exploration_sep7": len(train), "holdout_sep8": len(holdout)},
        "train_medians_fixed_sep7": medians,
        "broad": broad,
        "chain_provider": strata,
        "raw_missing_vs_zero_audit": raw_result,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"episodes": result["episodes"], "excluded": result["excluded"], "medians": medians, "raw_audit": result["raw_missing_vs_zero_audit"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
