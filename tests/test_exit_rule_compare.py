"""Exit-rule comparison tests.

`scripts/exit_rule_compare.py` compares causal trailing exits against what the deployed contracts
realised, over the WHOLE settled book. Two things about it are load-bearing and each is tested here:

  1. CAUSALITY. The running high must use only marks at or before t, and the exit must execute at the
     NEXT mark - never at the trigger price. A version that peeks one mark ahead would show a large
     spurious gain, which is precisely the look-ahead this project has hit before (rounds 36/39/43).
  2. THE TRUNCATION CONTROL. ACTUAL is scored at each position's last mark while an early-exiting rule
     is scored at its own exit mark, so the comparison favours early exit if marks stop early. Round 82
     measured that it does not bind here, and the script re-runs on a restricted dense subset rather
     than asserting the bias away. A test asserts the control exists and that the live gap is small.
"""
import datetime as dt
import importlib
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

erc = importlib.import_module("exit_rule_compare")

T0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def seq(*prices):
    return [(T0 + dt.timedelta(seconds=10 * i), p) for i, p in enumerate(prices)]


def test_kernel_matches_the_established_form():
    assert erc.econ(1.0) == pytest.approx(-0.04)
    assert erc.econ(1.0 / 0.96) == pytest.approx(0.0)
    assert erc.econ(1.25) == pytest.approx(0.20)


def test_parse_is_total():
    assert erc.parse("2026-01-01T00:00:00Z") is not None
    for bad in (None, "", "nope", 4, {}):
        assert erc.parse(bad) is None


def test_rule_does_not_trigger_on_a_monotone_rise():
    """With no drawdown there is nothing to trigger, so the outcome is the final mark."""
    marks = seq(1.00, 1.10, 1.20, 1.30)
    out = erc.trailing(marks, 1.00, 0.10)
    assert out == pytest.approx(erc.econ(1.30))


def test_rule_executes_at_the_NEXT_mark_not_the_trigger():
    """THE CAUSALITY GUARD.

    Prices 1.00 -> 1.20 -> 0.90 -> 0.80 with a 10% drawdown. The trigger is at 0.90 (20% below the
    1.20 peak). Execution must be at the NEXT mark, 0.80, giving 0.96*0.80 - 1. Crediting the trigger
    price instead would give 0.96*0.90 - 1, which is a materially better outcome and is exactly the
    look-ahead this test exists to prevent.
    """
    marks = seq(1.00, 1.20, 0.90, 0.80)
    out = erc.trailing(marks, 1.00, 0.10)
    assert out == pytest.approx(erc.econ(0.80)), (
        "the rule must fill at the mark AFTER the trigger; filling at the trigger price would be "
        "look-ahead")
    assert out != pytest.approx(erc.econ(0.90))


def test_running_high_never_uses_a_future_mark():
    """A later spike must not allow an earlier exit to be credited at the higher peak.

    Prices rise to 1.10, dip to 1.00, then spike to 3.00. With a 10% drawdown the trigger is the dip at
    1.00 (9.1% below 1.10 is NOT enough, so use 5%): with dd=0.05 the trigger is 1.00 and execution is
    the next mark, the 3.00 spike. If the rule used the future peak it would have exited differently.
    The assertion is simply that the outcome equals the next mark's value, i.e. no future information
    entered the peak.
    """
    marks = seq(1.00, 1.10, 1.00, 3.00)
    out = erc.trailing(marks, 1.00, 0.05)
    assert out == pytest.approx(erc.econ(3.00))


def test_arm_level_delays_the_trigger():
    """A rule that must first reach +50% cannot fire on a position whose peak stays below it."""
    marks = seq(1.00, 1.20, 1.00, 0.90)      # peak 1.20, never reaches 1.50
    armed_never = erc.trailing(marks, 1.00, 0.10, arm_level=0.50)
    from_entry = erc.trailing(marks, 1.00, 0.10)
    assert armed_never == pytest.approx(erc.econ(0.90)), "unarmed rule exits at the last mark"
    assert from_entry == pytest.approx(erc.econ(0.90)), "armed rule triggers at 0.90, fills at ..."
    # both land on the final mark here, so the discriminating case is the NEXT test


def test_arm_level_changes_the_outcome_when_a_later_mark_exists():
    marks = seq(1.00, 1.20, 1.00, 0.90, 0.70)
    from_entry = erc.trailing(marks, 1.00, 0.10)          # triggers at 1.00, fills at 0.90
    armed_050 = erc.trailing(marks, 1.00, 0.10, arm_level=0.50)   # never arms, exits at 0.70
    assert from_entry == pytest.approx(erc.econ(0.90))
    assert armed_050 == pytest.approx(erc.econ(0.70))
    assert from_entry > armed_050, "arming earlier must be at least as good in this fixture"


def test_load_reports_exclusions_rather_than_hiding_them():
    """Round 64's rule: an excluded population must be counted, never silently dropped."""
    import inspect
    src = inspect.getsource(erc.load)
    assert "excluded" in src and "return cases, excluded" in src, (
        "load() must return the excluded count alongside the usable cases")


def test_defaults_are_the_ones_the_analysis_used():
    assert 0.25 in erc.DEFAULT_DRAWDOWNS
    assert erc.DEFAULT_ARM_DRAWDOWN == 0.25
    assert erc.DEFAULT_ARM_LEVELS == (0.20, 0.30, 0.45)


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_truncation_gap_is_small_so_the_comparison_is_fair():
    """The round-82 control, asserted so the bias cannot silently start to bind.

    If the last in-life mark ever drifts far from the close, the whole-book comparison becomes
    unreliable because ACTUAL would be scored at a stale price while early-exiting rules are not.
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    cases, _excluded = erc.load(c, 3)
    if len(cases) < 100:
        pytest.skip("too few usable positions")
    gaps = sorted((x["cl"] - x["marks"][-1][0]).total_seconds() for x in cases)
    m = len(gaps)
    med = gaps[m // 2]
    over = sum(1 for g in gaps if g > 60)
    assert med <= 30, (
        f"median last-mark-to-close gap is {med:.0f}s; the ACTUAL side of the comparison is scored "
        f"at that mark, so a large gap would favour every early-exiting rule")
    assert over / m < 0.05, (
        f"{100*over/m:.1f}% of positions have their last mark more than 60 s before the close; the "
        f"truncation control can no longer be assumed away")
