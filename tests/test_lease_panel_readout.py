"""Lease-panel readout tests.

`scripts/lease_panel_readout.py` reads `kv['chain-meme-pattern-watch:leases145']`, the observation
scheduler's own checkpoint. Three things about that panel are easy to get wrong and each one changes
the conclusion, so each gets a test:

  1. SHAPE. `leases` is a LIST of items, not a `{token: item}` mapping. An earlier probe assumed the
     mapping and reported "lease items found: 0" while the panel held real data.
  2. UNIT. `mature_window_counts` counts distinct (token, window) PHASE TRANSITIONS, one per
     maturity, not distinct tokens, and only for tokens admitted to the observer. The column sums
     are therefore not a population; only within-row shares are comparable.
  3. MEANING. `SOURCE_NO_UPDATE` and `UNKNOWN_PATH_GAP` are different failures with opposite fixes:
     the first says the source never answered, the second says the frames arrived but continuity
     failed. Reporting either as "observation is broken" loses the distinction the panel exists to
     provide.
"""
import datetime as dt
import importlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

lpr = importlib.import_module("lease_panel_readout")


def test_percentile_is_bounded_and_ordered():
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert lpr.percentile(vals, 0.0) == 10.0
    assert lpr.percentile(vals, 0.99) == 50.0
    assert lpr.percentile(vals, 0.5) <= lpr.percentile(vals, 0.9)
    assert lpr.percentile([], 0.5) is None


def test_parse_is_total():
    assert lpr.parse("2026-01-01T00:00:00Z") is not None
    for bad in (None, "", "nope", 5, {}):
        assert lpr.parse(bad) is None


def test_lease_key_names_are_the_persisted_ones():
    """The three keys the panel lives under. Renaming one silently empties the readout."""
    assert lpr.LEASE_KEY == "chain-meme-pattern-watch:leases145"
    assert lpr.WATCH_KEY == "chain-meme-pattern-watch"
    assert lpr.COVERAGE_KEY == "coverage145:status"


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_panel_shape_is_a_list_and_carries_the_fields_we_read():
    """Guards mistake 1: `leases` must be a list, and the fields the readout depends on must exist.

    If this ever becomes a mapping the readout prints nothing useful, which is exactly the failure
    that happened during round 74 and looked like "the panel is empty".
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    row = c.execute("select value_json from kv where key=?", (lpr.LEASE_KEY,)).fetchone()
    if row is None:
        pytest.skip("lease panel not yet written")
    obj = json.loads(row["value_json"])
    leases = obj.get("leases")
    assert isinstance(leases, list), (
        f"expected `leases` to be a list, got {type(leases).__name__}; an earlier probe assumed a "
        f"dict and reported zero items on a non-empty panel")
    if not leases:
        pytest.skip("panel currently holds no leases")
    it = leases[0]
    assert isinstance(it, dict)
    for field in ("frame_count", "admitted_at", "min_observe_until"):
        assert field in it, f"lease item lost the field {field!r} the readout reports"
    # frame delays only appear once a 2nd/3rd frame lands, so they are checked across the whole set
    assert any("frame2_delay_seconds" in x or "frame3_delay_seconds" in x for x in leases), (
        "no lease carries a frame delay; the delay table would be empty")


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_mature_window_counts_are_within_row_normalisable():
    """Guards mistake 2: the test asserts only what the caveat allows.

    Every window row must carry the three outcome keys so a within-row share is computable, and the
    test deliberately does NOT assert anything about column totals, because those sum phase
    transitions rather than tokens.
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    row = c.execute("select value_json from kv where key=?", (lpr.LEASE_KEY,)).fetchone()
    if row is None:
        pytest.skip("lease panel not yet written")
    counts = (json.loads(row["value_json"]) or {}).get("mature_window_counts") or {}
    if not counts:
        pytest.skip("no matured windows yet")
    per = {}
    for k, v in counts.items():
        w, _, outcome = str(k).partition(":")
        per.setdefault(w, {})[outcome] = v
    assert "30" in per, "the 30 s window is the one the dominant gate tests; it must be present"
    for w, d in per.items():
        missing = {"OBSERVED", "SOURCE_NO_UPDATE", "UNKNOWN_PATH_GAP"} - set(d)
        assert not missing, f"window {w}s is missing outcome keys {sorted(missing)}"
        assert sum(d.values()) > 0


def test_the_two_failure_outcomes_are_documented_as_distinct():
    """Guards mistake 3: the readout's docstring must keep the distinction.

    These two verdicts have opposite remedies - one says the source never answered, the other says
    the frames arrived and continuity failed - so a readout that blurs them would misdirect the next
    round. The check is on the module text because that is where the distinction is communicated.
    """
    doc = lpr.__doc__ or ""
    # Normalise whitespace first: a phrase can straddle a line wrap in the docstring, and asserting
    # on the raw text made this test fail on a caveat that was in fact present.
    flat = " ".join(doc.split())
    for token in ("SOURCE_NO_UPDATE", "UNKNOWN_PATH_GAP"):
        assert token in flat, f"{token} must be explained in the module docstring"
    assert "did not answer" in flat or "never answered" in flat
    assert "continuity" in flat or "path" in flat
    # and the unit caveat must be present, since the table invites a wrong reading
    assert "NOT distinct tokens" in flat, (
        "the window table's unit caveat must be in the docstring: column sums are phase "
        "transitions, not tokens")


def test_the_panel_truncation_caveat_is_documented():
    """The round-86 correction, guarded.

    `observation_leases145.dump_state(watch, now, *, limit: int = 30)` caps the checkpoint at 30 rows
    and `bounded_summary` defaults to the same limit, so any count of leases read from the persisted
    panel is a LOWER BOUND. Round 86 first printed 'live leases: 9' as though it were the population.
    The module docstring must keep that caveat so the next reader does not repeat it.
    """
    doc = " ".join((lpr.__doc__ or "").split())
    assert "LOWER BOUND" in doc or "lower bound" in doc, (
        "the module docstring must state that the persisted lease count is a lower bound")
    assert "limit: int = 30" in doc or "limit=30" in doc, (
        "the docstring must name the parameter that truncates the panel")


def test_the_min_observe_until_filter_is_documented_as_the_binding_one():
    """The round-87 correction.

    `dump_state` skips any item whose `min_observe_until` has passed (observation_leases145.py:301-303),
    and that deadline is `admitted_at + 120 s` (EARLY_LEASE_SECONDS) extended only on a phase
    transition. Round 87 measured the live panel holding 4-8 rows while the watch reported 30 occupied
    candidate slots, so this filter -- not the 30-row limit -- is what bounds the panel. The docstring
    must say both, and must say the panel therefore over-represents fresh leases, because "lower bound"
    alone invites the reader to treat it as a random sample.
    """
    doc = " ".join((lpr.__doc__ or "").split())
    assert "min_observe_until" in doc, (
        "the docstring must name the filter that actually bounds the panel")
    assert "120" in doc, "the docstring must give the 120 s early-lease deadline it comes from"
    assert "OVER-represents" in doc or "over-represents" in doc, (
        "the docstring must state that the panel is biased toward fresh leases, not merely short")


def test_candidate_slot_caps_match_the_runtime_constants():
    """The occupancy readout compares against base_caps; if these drift the FULL flags are wrong."""
    sys.path.insert(0, str(ROOT / "src"))
    obs = importlib.import_module("memetrader.observation_leases145")
    assert obs.BASE_CAPS == {"early": 3, "growth": 4, "mature": 3}
    assert obs.CHAIN_CAP == 10


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_candidate_slots_are_mostly_at_cap():
    """The measurement that makes the user's budget decision concrete.

    `non_held_by_chain_bucket` is computed in memory from the same counter that gates admission
    (runtime.py:8148-8150 against runtime.py:7894-7898), so unlike the truncated lease list it IS a
    direct read of runtime state. If most buckets are NOT full then candidates are no longer queueing
    behind the cap - which would mean the slot budget is not the binding constraint, and that would be
    worth re-examining rather than ignoring.
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    row = c.execute("select value_json from kv where key=?", (lpr.WATCH_KEY,)).fetchone()
    if row is None:
        pytest.skip("watch panel not yet written")
    nhb = (json.loads(row["value_json"]) or {}).get("non_held_by_chain_bucket") or {}
    if not nhb:
        pytest.skip("no bucket occupancy recorded")
    caps = {"early": 3, "growth": 4, "mature": 3}
    full = total = 0
    for _chain, buckets in nhb.items():
        for bucket, occ in (buckets or {}).items():
            cap = caps.get(bucket, 0)
            total += 1
            if cap and occ >= cap:
                full += 1
    assert total > 0
    assert full / total >= 0.5, (
        f"only {full}/{total} candidate buckets are at cap; if occupancy has genuinely fallen the "
        f"slot budget stops being the binding constraint")
