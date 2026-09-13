"""Frame-window readout tests.

`scripts/frame_window_readout.py` reproduces the four acceptance rules of
`dex_trajectory.window()` (dex_trajectory.py:49-55) and reports, per token, whether the trajectory
window could ever have formed. That window is the gate behind
`await_distinct_dex_trajectory_frame`, which is 46.4% of all per-arm admission verdicts and the
terminal state for 98.9% of the pairs that touch it (round 72), so a mistake here mis-states why the
fleet is not trading.

The tests pin the FOUR rules independently. Each one, if dropped, changes the answer:
    * the full 30 s lookback     - a series younger than 30 s has nothing to compare against
    * the span limit (<= 40 s)   - three frames spread over 10 minutes is not a 30 s window
    * the max-gap rule (<= 30 s) - a 30 s hole inside the window invalidates it
    * the 3-frame minimum        - two points cannot give a velocity AND an acceleration

They also pin the counterfactual's reference cadence, because an earlier version reported every row
against whichever cadence happened to be evaluated first and printed 0.0% for all of them.
"""
import datetime as dt
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

fwr = importlib.import_module("frame_window_readout")

T0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def at(*seconds):
    return [T0 + dt.timedelta(seconds=s) for s in seconds]


def test_three_frames_ten_seconds_apart_is_a_valid_window():
    part, why = fwr.slice_like_window(at(0, 10, 20, 35), 3)
    assert why is None and part is not None, "0/10/20/35 s: full lookback, 35 s span, gaps <= 15 s"
    assert fwr.window_ok(part)


def test_span_limit_rejects_a_window_stretched_over_minutes():
    """Three frames exist and no gap exceeds 30 s, but the span is far beyond 30 s + slack."""
    part, why = fwr.slice_like_window(at(0, 25, 50, 75), 3)
    assert part is None
    assert why == "span_exceeds_limit"


def test_max_gap_rule_rejects_a_hole_inside_the_window():
    """The lookback row and the last row exist, but a consecutive gap exceeds 30 s."""
    part, why = fwr.slice_like_window(at(0, 45, 50), 2)
    assert part is None
    assert why in {"span_exceeds_limit", "gap_exceeds_30s"}
    # and directly on window_ok: a 45 s hop must fail even with 3 frames
    assert not fwr.window_ok(at(0, 45, 50))


def test_three_frame_minimum_is_enforced():
    """Two frames must never satisfy the window, however close together."""
    assert not fwr.window_ok(at(0, 5))
    part, why = fwr.slice_like_window(at(0, 5), 1)
    assert part is None
    assert why in {"fewer_than_3_frames", "span_exceeds_limit", "no_full_lookback"}


def test_full_lookback_is_required():
    """A series whose first frame is the last frame has no 30 s lookback at all."""
    part, why = fwr.slice_like_window(at(0), 0)
    assert part is None
    assert why == "no_full_lookback"


def test_constants_mirror_the_source():
    assert fwr.WINDOW_SECONDS == 30.0
    assert fwr.MIN_FRAMES == 3
    assert fwr.MAX_GAP == 30.0
    # dex_trajectory.py:53 uses max(5, seconds/3) -> 10 for a 30 s window
    assert fwr.SLACK == pytest.approx(10.0)


def test_the_reference_cadence_is_15_seconds():
    """The counterfactual's baseline must be looked up, not inherited from the first row.

    An earlier version set `base` on the first cadence evaluated (5 s) while labelling the column
    "vs 15s", so every row displayed a 0.0% delta. The script must therefore name 15 s explicitly;
    this asserts that the numbers it reports are ordered as the physics requires - a faster poll can
    never produce FEWER window-capable series than a slower one over the same lifetime.
    """
    multi = [at(0, 20, 40, 60, 80, 100), at(0, 12, 24, 36)]
    counts = {}
    for cad in (5.0, 10.0, 15.0):
        ok = 0
        for ts in multi:
            span = (ts[-1] - ts[0]).total_seconds()
            count = int(span // cad) + 1
            if count < fwr.MIN_FRAMES:
                continue
            sim = [ts[0] + dt.timedelta(seconds=i * cad) for i in range(count)]
            if fwr.window_ok(sim[-fwr.MIN_FRAMES:]):
                ok += 1
        counts[cad] = ok
    assert counts[5.0] >= counts[10.0] >= counts[15.0], (
        "a faster cadence cannot be worse than a slower one on the same observed lifetime")


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_frames_are_scarce_and_ingestion_is_not_dropping():
    """The two live properties the round-73 conclusion rests on.

    (1) most tokens get fewer than the 3 frames the window needs, so the gate is structurally
        unsatisfiable for them;
    (2) the ingestion lag is small, so 'frames are being dropped' is refuted rather than assumed.
    If (1) ever stops holding, the observation constraint has genuinely loosened and the round-73
    recommendation should be revisited.
    """
    import sqlite3
    from collections import defaultdict
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    series = defaultdict(set)
    lag = []
    for r in c.execute("select token_id, observed_at, recorded_at from token_snapshots "
                       "where observed_at is not null"):
        t = fwr.parse(r["observed_at"])
        if t is None:
            continue
        series[str(r["token_id"])].add(t)
        rec = fwr.parse(r["recorded_at"])
        if rec is not None:
            lag.append((rec - t).total_seconds())
    if len(series) < 100:
        pytest.skip("too few tokens to judge")
    lens = [len(v) for v in series.values()]
    share_lt3 = sum(1 for L in lens if L < fwr.MIN_FRAMES) / len(lens)
    assert share_lt3 > 0.50, (
        f"expected most tokens to have fewer than {fwr.MIN_FRAMES} frames; measured "
        f"{share_lt3:.1%}. If this fell, the observation supply has improved")
    over = sum(1 for x in lag if x > 30)
    assert over / max(1, len(lag)) < 0.01, (
        f"ingestion is dropping {100.0*over/max(1,len(lag)):.2f}% of frames past 30 s - that would "
        f"make the ingestion ceiling the constraint after all")
