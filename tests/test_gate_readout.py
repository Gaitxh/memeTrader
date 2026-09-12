"""Gate-readout tests.

The load-bearing part of `scripts/gate_readout.py` is the economic-return kernel, because round
120-52 found that the intuitive form

    (1 - BUY)/(1 + SELL) * R - 1 - 2*fee_bps/1e4

is WRONG: `entry_execution_price_usd` already contains the 4% buy slippage, so dividing by (1+SELL)
charges it twice, and the deployed settings carry no additional per-fill fee. That form matched the
engine's own recorded values 0 times out of 1,300, while `0.96*R - 1` matched exactly 1,265 times.
It made a point estimate move by two orders of magnitude.

So the kernel is asserted against the engine's own recorded numbers when a live database is
available, and against closed-form values otherwise. A readout that silently reverts to the wrong
formula would be worse than no readout, because it would look authoritative.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gate_readout as gr  # noqa: E402


def test_kernel_closed_form():
    assert gr.economic_return(1.0) == pytest.approx(-0.04), "a flat price returns -4% after the sell haircut"
    assert gr.economic_return(1.25) == pytest.approx(0.20), "0.96*1.25 - 1"
    assert gr.economic_return(1.0 / 0.96) == pytest.approx(0.0), "break-even price ratio"


def test_the_wrong_formula_is_actually_different():
    """Guards the specific regression: the two forms must not coincide."""
    def wrong(r):
        return (1 - 0.04) / (1 + 0.04) * r - 1 - 2 * 60 / 1e4

    for ratio in (1.10, 1.20, 1.30):
        assert abs(gr.economic_return(ratio) - wrong(ratio)) > 0.02, (
            "the corrected and previously-used kernels must differ measurably; if they no longer "
            "do, this test is no longer protecting anything"
        )
    # and the wrong form is STRICTER, i.e. it under-fires a take-profit
    assert wrong(1.25) < gr.economic_return(1.25)


def test_bookkeeping_reasons_are_separated_from_decisions():
    assert "cohort_observation" in gr.BOOKKEEPING
    assert "pattern_observation" in gr.BOOKKEEPING
    # these are real decisions and must NOT be classed as bookkeeping
    for reason in ("no_active_matching_entry_policy", "entry_pool_liquidity_below_configured_floor",
                   "entry_pool_liquidity_absent_curve_stage", "entry_snapshot_too_old"):
        assert reason not in gr.BOOKKEEPING


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_kernel_matches_the_engines_own_recorded_values():
    """The decisive check: the engine stores what IT computed, so `0.96*R - 1` must reproduce it.

    Only marks whose position supplies an entry price can be scored, and a small minority are
    excluded by a position-join mismatch, so the assertion is on the exact-match RATE rather than
    on every row.
    """
    db = sqlite3.connect(str(ROOT / "data" / "memetrader_forward.sqlite3"))
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """select m.trigger_evidence_json, p.entry_execution_price_usd ep
           from chain_meme_trader_marks m
           join chain_meme_trader_positions p
             on p.arm_id = m.arm_id and p.shadow_cohort_id = m.shadow_cohort_id
           where m.trigger_evidence_json like '%economic_return%'
           limit 400""").fetchall()
    if not rows:
        pytest.skip("no marks carrying pre_trigger.economic_return")

    import json
    exact = scored = 0
    for r in rows:
        try:
            pre = (json.loads(r["trigger_evidence_json"]) or {}).get("pre_trigger") or {}
            recorded = float(pre["economic_return"])
            ratio = float(pre["price_usd"]) / float(r["ep"])
        except (TypeError, ValueError, KeyError, ZeroDivisionError):
            continue
        if ratio <= 0:
            continue
        scored += 1
        if abs(gr.economic_return(ratio) - recorded) < 1e-9:
            exact += 1
    assert scored >= 50, f"too few scorable marks to judge the kernel ({scored})"
    rate = exact / scored
    assert rate > 0.90, (
        f"the corrected kernel reproduced the engine's own recorded economic_return in only "
        f"{exact}/{scored} ({rate:.0%}) - it may have been changed back to the double-charging form"
    )
