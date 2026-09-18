"""Tests for the paired A/B instrument.

This tool is what the project's whole governance rule rests on -- ">=30 independent tokens, a
paired comparison, and a negative after-cost result" -- so its two failure modes are worth pinning:

  1. PAIRING ON THE WRONG UNIT. Pairing on cohort is the stronger design (same frozen signal),
     but it silently reports ZERO pairs when the arms structurally cannot share one. Measured
     2026-09-14 on `demand_floor153_d47_v1` against its control: all 10 of the new arm's tokens had
     also been traded by the control, yet at different cohorts, because the control carries
     `single_token_lifetime_entry` and had consumed those tokens before the new arm existed. Under
     the old tool that arm could never be judged at all.
  2. COUNTING SETTLED POSITIONS AS SAMPLE SIZE. The independent unit is the TOKEN; positions are
     inflated by fan-out (p50 41 positions per token on this epoch).

Both are pinned here, plus the direction convention, because a sign error would invert every
conclusion the tool produces.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import paired_arm_ab as tool  # noqa: E402


def _row(arm, token, cohort, pnl, status="closed", opened="2026-09-14T00:00:00Z"):
    return {"arm_id": arm, "token_id": token, "shadow_cohort_id": cohort,
            "realized_pnl_usd": pnl, "status": status, "opened_at": opened,
            "stake_usd": 20.0, "close_reason": "closed"}


def test_token_mode_pairs_arms_that_can_never_share_a_cohort():
    rows = [
        _row("control", "tok-a", 1, 5.0, opened="2026-09-14T00:00:00Z"),
        _row("arm", "tok-a", 9, 8.0, opened="2026-09-14T01:00:00Z"),
        _row("control", "tok-b", 1, -5.0, opened="2026-09-14T00:00:00Z"),
        _row("arm", "tok-b", 9, -2.0, opened="2026-09-14T01:00:00Z"),
    ]
    assert tool.paired(rows, "control", "arm", pair_on="cohort") == []
    diffs = tool.paired(rows, "control", "arm", pair_on="token")
    assert len(diffs) == 2
    # difference is A - B, so a NEGATIVE mean means arm B did better
    assert {d["token_id"]: round(d["difference"], 2) for d in diffs} == {
        "tok-a": -3.0, "tok-b": -3.0}


def test_token_mode_takes_each_arms_first_position_so_fanout_cannot_inflate_n():
    rows = [
        _row("control", "tok-a", 1, 100.0, opened="2026-09-14T02:00:00Z"),
        _row("control", "tok-a", 2, 1.0, opened="2026-09-14T00:00:00Z"),
        _row("control", "tok-a", 3, 1.0, opened="2026-09-14T01:00:00Z"),
        _row("arm", "tok-a", 9, 2.0, opened="2026-09-14T03:00:00Z"),
        _row("arm", "tok-a", 10, 2.0, opened="2026-09-14T04:00:00Z"),
    ]
    diffs = tool.paired(rows, "control", "arm", pair_on="token")
    assert len(diffs) == 1, "one token must contribute exactly one pair"
    # the FIRST position of each arm decides: control 1.0 (00:00) vs arm 2.0 (03:00)
    assert round(diffs[0]["difference"], 2) == -1.0


def test_open_positions_never_enter_the_paired_set():
    rows = [
        _row("control", "tok-a", 1, 5.0),
        _row("arm", "tok-a", 1, 8.0, status="open"),
    ]
    assert tool.paired(rows, "control", "arm", pair_on="cohort") == []
    assert tool.paired(rows, "control", "arm", pair_on="token") == []


def test_cohort_mode_still_requires_both_arms_in_the_same_cohort():
    rows = [
        _row("control", "tok-a", 7, 5.0),
        _row("arm", "tok-a", 7, 8.0),
        _row("control", "tok-b", 8, -5.0),
    ]
    diffs = tool.paired(rows, "control", "arm", pair_on="cohort")
    assert len(diffs) == 1 and diffs[0]["cohort"] == 7
    assert round(diffs[0]["difference"], 2) == -3.0


def test_the_agreed_bar_is_thirty_independent_tokens_not_twenty_positions():
    assert tool.MIN_SETTLED_PER_SIDE == 30
    source = Path(tool.__file__).read_text(encoding="utf-8")
    # readiness must be computed from token counts, never from settled-position counts
    assert "a_stats['tokens'] >= args.min_tokens" in source
    assert "paired_tokens >= args.min_tokens" in source
    assert "a_stats['settled'] >= MIN_SETTLED_PER_SIDE" not in source


def test_default_minimum_is_thirty_and_configurable():
    import argparse

    parser_source = Path(tool.__file__).read_text(encoding="utf-8")
    assert "'--min-tokens'" in parser_source
    assert "default=MIN_SETTLED_PER_SIDE" in parser_source
    assert "'--pair-on'" in parser_source
    assert "choices=('cohort', 'token', 'source_buy')" in parser_source


def test_the_clustered_interval_and_leave_one_out_use_tokens():
    """A clustered bootstrap that resampled POSITIONS would understate the interval badly."""
    rows = []
    for i in range(12):
        for j in range(5):  # five positions per token: fan-out
            rows.append(_row("control", f"tok-{i}", i*5+j, -1.0*j, opened=f"2026-09-14T00:{j:02d}:00Z"))
            rows.append(_row("arm", f"tok-{i}", i*5+j, -1.0*j-.5, opened=f"2026-09-14T00:{j:02d}:00Z"))
    diffs = tool.paired(rows, "control", "arm", pair_on="token")
    assert len(diffs) == 12
    ci = tool.clustered_interval(diffs, iterations=200)
    assert ci is not None and ci[0] <= ci[1]
    loo = tool.leave_one_token_out(diffs)
    assert loo is not None and loo["full_mean"] is not None


def test_json_report_names_the_pairing_unit_and_both_sample_sizes():
    source = Path(tool.__file__).read_text(encoding="utf-8")
    for key in ("'pair_on'", "'paired_units'", "'paired_tokens'",
                "'minimum_independent_tokens'"):
        assert key in source, key
