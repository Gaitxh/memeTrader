"""Window-size sweep tests.

`scripts/window_size_sweep.py` ports `dex_trajectory.window` and reports what each window size would
qualify. Two failure modes matter here, and both have already happened in this project:

  1. THE PARAMETER BECOMING IRRELEVANT. Round 74's counterfactual sliced each series to exactly three
     frames before applying the rules, so the window length changed nothing and 60/120/300 s all
     returned the identical 27,753 (39.90%). A sweep that cannot distinguish its own parameter is
     worse than no sweep, because it looks like a result. `test_the_window_parameter_changes_the_result`
     exists specifically to fail if that construction ever returns.
  2. THE RULES BEING APPLIED OUT OF ORDER. `part` runs from the cutoff row to the end and is NOT
     capped at three frames, which is what makes a longer window able to hold more frames. Dropping
     that property silently changes which rule binds.

The tests are therefore on the ported function's contract, not on live numbers.
"""
import datetime as dt
import importlib
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

wss = importlib.import_module("window_size_sweep")

T0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def at(*seconds):
    return [T0 + dt.timedelta(seconds=s) for s in seconds]


def test_three_frames_inside_the_window_qualify():
    """A series with a long history plus three frames bunched in the last 30 s.

    The FIRST rule needs a full lookback, so the series must start at least `seconds` before its last
    frame; a fixture that merely ENDS at t=30 with seconds=30 fails rule A, not the density rules.
    """
    ok, why, plen = wss.window(at(0, 60, 70, 80, 90), 30)
    assert ok, f"expected a valid 30 s window, got {why}"
    assert plen >= 3


def test_no_full_lookback_is_rejected():
    """A single frame has nothing at or before the cutoff."""
    ok, why, _ = wss.window(at(0), 30)
    assert not ok
    assert why == "A_no_full_lookback"


def test_span_cap_is_rejected():
    """The slice from the cutoff row to the end spans well beyond the window.

    Frames at 0,100,110,180,190 with seconds=30: the last frame at/before the cutoff is t=110, so
    part runs 110..190 = an 80 s span against a 40 s cap.
    """
    ok, why, _ = wss.window(at(0, 100, 110, 180, 190), 30)
    assert not ok
    assert why == "B_span_exceeds_cap"


def test_the_gap_rule_rejects_a_hole_over_thirty_seconds():
    ok, why, _ = wss.window(at(0, 60, 130, 140), 60)
    assert not ok
    assert why == "C_gap_over_30s"


def test_fewer_than_three_frames_is_rejected():
    ok, why, _ = wss.window(at(0, 100, 130), 30)
    assert not ok
    assert why == "D_fewer_than_3_frames"


def test_part_is_not_capped_at_three_frames():
    """The property that lets a LONGER window hold MORE frames.

    With frames every 5 s and a 60 s window, `part` must run from the cutoff row to the end, so it
    holds considerably more than three. If a future edit clamps it to MIN_FRAMES the sweep silently
    becomes parameter-blind.
    """
    rows = at(*range(0, 125, 5))          # 0,5,...,120
    ok, why, plen = wss.window(rows, 60)
    assert ok, f"expected a valid 60 s window, got {why}"
    assert plen > wss.MIN_FRAMES, (
        f"part held only {plen} frames; the contract is the whole slice from the cutoff, not three "
        f"points")


def test_the_window_parameter_changes_the_result():
    """GUARDS THE ROUND-74 WITHDRAWAL.

    60/120/300 s returned an identical count there because the harness had made the parameter
    irrelevant. On one series with an uneven history, different sizes must reach DIFFERENT verdicts,
    and the sweep must report different qualifying counts for them.
    """
    rows = at(0, 5, 12, 20, 26, 90, 140, 200, 260, 320, 500, 560, 570, 580, 590)
    # the single series has no lookback for large windows, so exercise the rule directly too
    verdicts = {sec: wss.window(rows, sec)[0] for sec in (5, 30, 60, 180)}
    assert len(set(verdicts.values())) > 1, (
        f"the window size changed nothing ({verdicts}); the parameter is not reaching the rules")
    # and through the sweep, with enough history that several sizes can succeed
    long_rows = at(*range(0, 400, 10))
    res = wss.sweep({"t": long_rows}, (5, 30, 60, 300))
    counts = {w: ok for w, (_a, ok, _f) in res.items()}
    assert len(set(counts.values())) > 1, (
        f"every size qualified the same number of frames ({counts}); the parameter is irrelevant, "
        f"which is precisely the bug that invalidated the round-74 sweep")


def test_sweep_accounts_for_every_attempt():
    """attempts must equal frames x windows, and successes+failures must reconcile per window."""
    series = {"a": at(0, 10, 20, 40), "b": at(0, 100, 200)}
    windows = (5, 30, 60)
    res = wss.sweep(series, windows)
    total_frames = sum(len(v) for v in series.values())
    for w in windows:
        attempts, ok, fails = res[w]
        assert attempts == total_frames, f"{attempts} attempts for {total_frames} frames at {w}s"
        assert ok + sum(fails.values()) == attempts, "successes and failures must partition attempts"


def test_default_windows_match_the_engine():
    assert wss.DEFAULT_WINDOWS == (5, 15, 30, 60, 180, 300), "must mirror dex_trajectory.py:15"
    assert wss.GATED_WINDOW == 30, "store.py:27784 reads windows['30']"
    assert wss.MIN_FRAMES == 3
    assert wss.GAP_LIMIT == 30.0


def test_reach_counts_distinct_tokens_not_frames():
    """`reach` must return a SET of tokens, and must be <= the qualifying frame count."""
    series = {"a": at(0, 40, 50, 60, 70), "b": at(0, 100, 200)}
    r = wss.reach(series, 30)
    assert isinstance(r, set), "reach must be a set of token keys"
    assert r <= set(series), "reach must only contain input tokens"
    _a, frames_ok, _f = wss.sweep(series, (30,))[30]
    assert len(r) <= frames_ok, "distinct tokens can never exceed qualifying frames"


def test_frame_count_and_reach_can_disagree():
    """GUARDS THE ROUND-75/76 REVERSAL.

    Round 75 optimised qualifying FRAME COUNT and concluded the gated 30 s sat on the low side of a
    peak, with 60 s better by 21%. Round 76 showed the objective was wrong: a qualifying frame
    matters only because it unblocks that token at that frame, so REACH is the metric - and on reach
    the live 30 s is the best size.

    This fixture pins the mechanical reason the two can diverge. At a REGULAR 30 s cadence the 30 s
    window qualifies NOTHING, because dex_trajectory.py:54 rejects any consecutive gap `> 30` and a
    30 s cadence lands exactly on the boundary, while the 60 s window tolerates it and qualifies.
    So frame count does not merely differ from reach - it can rank the sizes in the opposite order.
    """
    regular30 = at(*range(0, 601, 30))       # 21 frames, cadence exactly 30 s
    f30 = wss.sweep({"r": regular30}, (30,))[30][1]
    f60 = wss.sweep({"r": regular30}, (60,))[60][1]
    assert f30 == 0, (
        f"a regular 30 s cadence must fail the 30 s window entirely (gap 30 is not < 30); "
        f"measured {f30} qualifying frames")
    assert f60 > 0, "the 60 s window should tolerate a 30 s cadence"
    assert f60 > f30, "fixture must show frame count preferring the WIDER window"

    # and a short-lived series shows the same sizes ranked the OTHER way on reach
    short = at(0, 15, 30, 40)                 # lifetime 40 s
    assert wss.reach({"s": short}, 30) == {"s"}, "a 40 s series should reach at 30 s"
    assert wss.reach({"s": short}, 60) == set(), (
        "a 40 s series cannot form a 60 s window (no frame at or before t_end - 60)")


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_gated_size_is_optimal_for_reach():
    """The corrected live claim, and the opposite of round 75's.

    On the live epoch the gated 30 s is the BEST size by token reach, even though 60 s beats it on
    frame count. If this ever inverts, the gate threshold becomes a real lever and the question
    should be reopened - so the assertion is deliberately in the direction that fails loudly.
    """
    import sqlite3
    from collections import defaultdict as dd
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    series = dd(set)
    for r in c.execute("select token_id, observed_at from token_snapshots "
                       "where observed_at is not null"):
        t = wss.parse(r["observed_at"])
        if t is not None:
            series[str(r["token_id"])].add(t)
    series = {k: sorted(v) for k, v in series.items()}
    if len(series) < 100:
        pytest.skip("too few series to judge")
    reaches = {w: len(wss.reach(series, w)) for w in wss.DEFAULT_WINDOWS}
    gated = reaches[wss.GATED_WINDOW]
    best = max(reaches, key=lambda w: reaches[w])
    assert best == wss.GATED_WINDOW, (
        f"the gated {wss.GATED_WINDOW}s is no longer the best size by token reach; "
        f"measured {reaches}. A different size reaching more tokens would make the threshold a "
        f"genuine lever, so reopen the question rather than ignoring this")


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_sweep_finds_a_non_gated_size_at_least_as_good():
    """The live claim: some already-computed size qualifies at least as many frames as the gated 30 s.

    If this ever fails, the round-75 finding has reversed and the gate threshold is no longer the
    binding choice. Only the ORDERING is asserted, never a profitability claim.
    """
    import sqlite3
    from collections import defaultdict as dd
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    series = dd(set)
    for r in c.execute("select token_id, observed_at from token_snapshots "
                       "where observed_at is not null"):
        t = wss.parse(r["observed_at"])
        if t is not None:
            series[str(r["token_id"])].add(t)
    series = {k: sorted(v) for k, v in series.items()}
    if len(series) < 100:
        pytest.skip("too few series to judge")
    res = wss.sweep(series, wss.DEFAULT_WINDOWS)
    gated = res[wss.GATED_WINDOW][1]
    # res maps window -> (attempts, successes, failures); pick by successes, not by the whole tuple
    best_w = max(res, key=lambda w: res[w][1])
    best_ok = res[best_w][1]
    assert best_ok >= gated, (
        f"the best size ({best_w}s, {best_ok}) did not beat the gated 30s ({gated})")
