"""Payload compaction of the per-arm `feature_vector` inside stored `cohort_signals`.

Measured 2026-09-13: `cohort_observation` rows were 582.2 MB of a 920.7 MB database (63%),
averaging 86,101 bytes; inside one 98 KB row `cohort_signals` was 81,188 bytes because it held
~16 entries each carrying the SAME ~7.5 KB `decision_evidence.feature_vector` - one vector
copied once per signalling arm. Growth was ~7 MB per 10 minutes (~1 GB/day).

Exactly TWO readers in the whole codebase consume that vector, and between them they touch only
three scalar fields:
    store.py `distinct_trajectory`  -> frozen['pair_address'], frozen['observed_at']
    mode_learning144.py             -> feature_vector.get('ingested_at')  (has a fallback)

These tests pin the contract: the stored form keeps those three, drops the rest, and never
mutates the caller's mapping.
"""
from __future__ import annotations

from memetrader import store as store_module


class _Fake:
    _COHORT_VECTOR_KEEP = store_module.Store._COHORT_VECTOR_KEEP
    _compact_cohort_signals_for_storage = (
        store_module.Store._compact_cohort_signals_for_storage)
    # `Store._json` is a staticmethod on the real class; bind it the same way.
    _json = staticmethod(store_module.Store._json)


def _features(n_arms: int = 3, bulk: int = 2000) -> dict:
    vector = {
        "pair_address": "0xpool",
        "observed_at": "2026-09-12T20:00:00Z",
        "ingested_at": "2026-09-12T20:00:01Z",
        "windows": {"30": {"return_fraction": 0.01, "acceleration": 0.2}},
        "current": {"price_usd": 1.5, "liquidity_usd": 20_000.0},
        "buy_count_share": 0.5,
        "interpretation": "x" * bulk,  # stands in for the bulk
    }
    return {
        "observed_at": "2026-09-12T20:00:00Z",
        "pair_address": "0xpool",
        "cohort_signals": {
            f"arm_{i}": {
                "decision_key": f"k{i}",
                "recorded_at": "2026-09-12T20:00:02Z",
                "decision_evidence": {
                    "signal_at": "2026-09-12T20:00:02Z",
                    "mode": f"kind_{i}",
                    "feature_vector": dict(vector),
                    "mechanism_flags": {"hot": True},
                },
            }
            for i in range(n_arms)
        },
    }


def test_the_three_consumed_fields_survive_untouched():
    """Both readers must keep working byte-for-byte."""
    fake = _Fake()
    stored = fake._compact_cohort_signals_for_storage(_features())
    for arm, signal in stored["cohort_signals"].items():
        evidence = signal["decision_evidence"]
        # store.py distinct_trajectory
        assert evidence["feature_vector"]["pair_address"] == "0xpool"
        assert evidence["feature_vector"]["observed_at"] == "2026-09-12T20:00:00Z"
        # mode_learning144
        assert evidence["feature_vector"]["ingested_at"] == "2026-09-12T20:00:01Z"
        assert evidence["signal_at"] == "2026-09-12T20:00:02Z"
        assert evidence["mode"].startswith("kind_")
        assert "mechanism_flags" not in evidence
        assert isinstance(evidence["mechanism_flags_ref"], int)
        assert signal["decision_key"]


def test_mechanism_flags_are_interned_losslessly():
    """Round 120-9: hoisting to row level was refuted; interning is the lossless alternative.

    Measured: within one real row, 36 arms carried FOUR distinct flag sets, because the
    accumulated cohort_signals mixes arms signalled on different frames. So each distinct set
    is stored once and every arm keeps an index into it.
    """
    import json

    fake = _Fake()
    features = _features(4)
    # Give two arms one flag set and two arms another, as the live data does.
    for i, arm in enumerate(sorted(features["cohort_signals"])):
        ev = features["cohort_signals"][arm]["decision_evidence"]
        ev["mechanism_flags"] = {"hot": True, "bucket": i // 2}
    stored = fake._compact_cohort_signals_for_storage(features)
    table = stored["cohort_mechanism_flags"]
    assert len(table) == 2, table
    # Every arm's original flags must be recoverable exactly.
    for arm, signal in stored["cohort_signals"].items():
        original = features["cohort_signals"][arm]["decision_evidence"]["mechanism_flags"]
        recovered = table[signal["decision_evidence"]["mechanism_flags_ref"]]
        assert recovered == original, arm
    # And the table itself is much smaller than the per-arm copies it replaces.
    before = sum(len(json.dumps(features["cohort_signals"][a]["decision_evidence"]
                               ["mechanism_flags"])) for a in features["cohort_signals"])
    after = len(json.dumps(stored["cohort_mechanism_flags"]))
    assert after < before * 0.6, (before, after)


def test_the_bulk_is_actually_removed():
    """At the measured real shape (~7.5 KB per arm, ~16 arms) the row shrinks by >85%.

    The measured production row was 98,339 bytes with `cohort_signals` at 81,188 and 16 arm
    entries of ~7,780 bytes each. `bulk=6000` reproduces that per-arm size.
    """
    import json

    fake = _Fake()
    original = _features(16, bulk=6000)
    stored = fake._compact_cohort_signals_for_storage(original)
    before = len(json.dumps(original, ensure_ascii=False))
    after = len(json.dumps(stored, ensure_ascii=False))
    assert after < before * 0.15, (before, after)
    for signal in stored["cohort_signals"].values():
        vector = signal["decision_evidence"]["feature_vector"]
        assert "windows" not in vector
        assert "current" not in vector
        assert "interpretation" not in vector
        assert "feature_vector_compacted" in signal["decision_evidence"]


def test_the_reduction_scales_with_the_arm_count():
    """The saving comes from removing a per-arm copy, so more arms means more saved."""
    import json

    fake = _Fake()
    ratios = []
    for arms in (2, 8, 16):
        original = _features(arms, bulk=6000)
        stored = fake._compact_cohort_signals_for_storage(original)
        before = len(json.dumps(original, ensure_ascii=False))
        after = len(json.dumps(stored, ensure_ascii=False))
        ratios.append(after / before)
    assert ratios == sorted(ratios, reverse=True), ratios


def test_the_caller_mapping_is_never_mutated():
    """Engines, mode_learning144 and the exit path must see the object they saw before."""
    fake = _Fake()
    original = _features()
    snapshot_evidence = original["cohort_signals"]["arm_0"]["decision_evidence"]
    before_keys = set(snapshot_evidence["feature_vector"])
    stored = fake._compact_cohort_signals_for_storage(original)
    assert set(snapshot_evidence["feature_vector"]) == before_keys, "in-memory vector changed"
    assert "windows" in snapshot_evidence["feature_vector"]
    assert stored is not original
    assert stored["cohort_signals"] is not original["cohort_signals"]


def test_shapes_that_do_not_apply_pass_through_unchanged():
    fake = _Fake()
    for value in (None, {}, {"cohort_signals": None}, {"cohort_signals": {}},
                  {"cohort_signals": {"arm": "not-a-mapping"}},
                  {"cohort_signals": {"arm": {"decision_evidence": {}}}},
                  {"cohort_signals": {"arm": {"decision_evidence": {"feature_vector": 5}}}}):
        out = fake._compact_cohort_signals_for_storage(value)
        assert isinstance(out, dict)
        if isinstance(value, dict):
            for k, v in value.items():
                assert out.get(k) == v


def test_a_vector_that_is_already_compact_is_left_alone():
    fake = _Fake()
    features = _features(1)
    vector = features["cohort_signals"]["arm_0"]["decision_evidence"]["feature_vector"]
    for k in list(vector):
        if k not in fake._COHORT_VECTOR_KEEP:
            vector.pop(k)
    out = fake._compact_cohort_signals_for_storage(features)
    assert "feature_vector_compacted" not in out["cohort_signals"]["arm_0"]["decision_evidence"]


def test_the_two_readers_still_work_against_a_compacted_row():
    """End-to-end shape check of the exact expressions the production readers use."""
    fake = _Fake()
    stored = fake._compact_cohort_signals_for_storage(_features())
    signals = stored["cohort_signals"]
    # store.py:28932-28934
    evidence = signals.get("arm_0", {}).get("decision_evidence", {})
    frozen = evidence.get("feature_vector", {})
    assert frozen and frozen.get("pair_address") and frozen["observed_at"]
    # store.py:28939 compares these timestamps, so they must parse
    from memetrader.models import parse_time
    parse_time(frozen["observed_at"])
    # mode_learning144.py:279
    assert signals.get("arm_0", {}).get("decision_evidence", {}).get(
        "feature_vector", {}).get("ingested_at")
