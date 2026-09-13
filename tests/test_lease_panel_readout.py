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
