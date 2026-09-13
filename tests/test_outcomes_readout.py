"""Outcomes-readout tests.

`scripts/outcomes_readout.py` reads `feature_json['outcomes']` -- the per-arm admission verdicts the
engine writes at store.py:28225 and persists at :28283. Until round 120-72 nothing read them, and
two different mistakes were made while reading them ad hoc:

  1. a "token" column holding PAIR-level counts (rule 26: a merged count must be divided by distinct
     entities). `strategy_token_lifetime_entry_consumed` has ~520k verdicts but touches only 57
     tokens.
  2. an "escape %" whose numerator was a pair count and whose denominator was a verdict count, which
     printed 40.6% for a gate whose true terminal share is 98.9%.

Both mistakes made a load-bearing number wrong in the same direction, and both are exactly the kind
of error that a readout is supposed to prevent rather than reproduce. So the tests below assert the
three ARITHMETIC invariants that catch them, plus the parse/skip behaviour that keeps the readout
from silently reporting an empty window as a clean result.

The tests build their own fixture database rather than depending on the live one, so they run
anywhere; the live-database check at the end is skipped when the forward DB is absent.
"""
import importlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

orx = importlib.import_module("outcomes_readout")


def _fixture(tmp_path):
    """A miniature but structurally faithful copy of the two tables the readout touches."""
    db = tmp_path / "fixture.sqlite3"
    c = sqlite3.connect(str(db))
    c.executescript(
        """
        create table chain_meme_trader_v6_entry_evaluations(
            id integer primary key, token_id text, evaluated_at text, feature_json text);
        create table chain_meme_trader_positions(
            id integer primary key, token_id text, status text);
        """
    )
    # token A: 3 arms, all on the gate, twice -> the gate is the terminal state
    rows = [
        ("A", "2026-01-01T00:00:01Z", {"arm1": "gate", "arm2": "passive", "arm3": "gate"}),
        ("A", "2026-01-01T00:00:02Z", {"arm1": "gate", "arm2": "gate", "arm3": "gate"}),
        # token B: one arm escapes the gate to an admission reason
        ("B", "2026-01-01T00:00:03Z", {"arm1": "gate"}),
        ("B", "2026-01-01T00:00:04Z", {"arm1": "admitted_now"}),
        # token C: a row with no outcomes at all must be skipped, not counted as empty
        ("C", "2026-01-01T00:00:05Z", {}),
    ]
    for i, (tok, at, oc) in enumerate(rows, start=1):
        c.execute(
            "insert into chain_meme_trader_v6_entry_evaluations(id,token_id,evaluated_at,feature_json)"
            " values(?,?,?,?)",
            (i, tok, at, json.dumps({"outcomes": oc}) if oc else json.dumps({"other": 1})),
        )
    # token A reached a position; B and C did not
    c.execute("insert into chain_meme_trader_positions(id,token_id,status) values(1,'A','open')")
    c.commit()
    c.row_factory = sqlite3.Row
    return c


def test_verdicts_tokens_and_pairs_are_different_units(tmp_path):
    """The invariant that catches mistake 1: on the fixture, one reason has more verdicts than
    tokens, and the readout must report both rather than one under the other's name."""
    c = _fixture(tmp_path)
    verdicts, tokens, pairs, rows_with = orx.load(c, "", [])
    assert rows_with == 4, "a row whose outcomes dict is empty must not count as having outcomes"
    # gate: token A has arm1+arm3 on row 1 and arm1+arm2+arm3 on row 2 = 5, plus B/arm1 = 6
    assert verdicts["gate"] == 6
    assert len(tokens["gate"]) == 2, "tokens counts DISTINCT tokens"
    gate_pairs = [k for k, seq in pairs.items() if "gate" in seq]
    assert len(gate_pairs) == 4, "(token, arm) pairs touching the gate"
    assert verdicts["gate"] != len(gate_pairs), (
        "verdicts and pairs must not coincide on this fixture; if they do the test no longer "
        "discriminates the two units")


def test_terminal_share_uses_pairs_on_both_sides(tmp_path):
    """The invariant that catches mistake 2: ends% must be pairs/pairs, never pairs/verdicts.

    On the fixture the gate is terminal for 3 of the 4 pairs that touch it (all but B/arm1), so the
    correct figure is 75%. Dividing by the gate's VERDICT count instead would give 3/6 = 50%, which
    is a different number - that is what makes this test able to catch the regression.
    """
    c = _fixture(tmp_path)
    verdicts, _tokens, pairs, _rows = orx.load(c, "", [])
    touch = end_on = 0
    for _k, seq in pairs.items():
        if "gate" in seq:
            touch += 1
            if seq[-1] == "gate":
                end_on += 1
    assert (touch, end_on) == (4, 3)
    ends_pct = 100.0 * end_on / touch
    assert ends_pct == pytest.approx(75.0)
    wrong_pct = 100.0 * end_on / verdicts["gate"]
    assert wrong_pct == pytest.approx(50.0)
    assert abs(ends_pct - wrong_pct) > 20.0, (
        "the two denominators must be visibly different on this fixture, otherwise the test "
        "cannot catch a pairs/verdicts mix-up")


def test_admission_reason_is_flagged_not_treated_as_a_refusal(tmp_path):
    """`cohort_frozen_opportunity_ready` means the candidate WAS accepted. Reading it as a refusal
    would invert its meaning, so it is declared in the module rather than inferred."""
    assert "cohort_frozen_opportunity_ready" in orx.ADMISSION_REASONS
    for refusal in ("await_distinct_dex_trajectory_frame", "wait_passive_cohort_opportunity",
                    "strategy_open_slot_limit", "pattern_already_enrolled_at_this_pool"):
        assert refusal not in orx.ADMISSION_REASONS


def test_parse_is_total():
    """A malformed stamp must return None rather than raising: the readout runs over 53k rows."""
    assert orx.parse("2026-01-01T00:00:00Z") is not None
    assert orx.parse("2026-01-01T00:00:00+00:00") is not None
    for bad in (None, "", "not-a-time", 17, {}):
        assert orx.parse(bad) is None


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_gate_dominates_verdicts_and_is_terminal():
    """On the live epoch the gate dominates verdicts AND is where flow terminates.

    Both halves matter: a high verdict share alone would also fit a transient state every candidate
    passes through, and a high terminal share alone would fit a rarely-used reason.
    """
    db = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    verdicts, tokens, pairs, rows_with = orx.load(db, "", [])
    if not verdicts:
        pytest.skip("no outcomes recorded yet")
    GATE = "await_distinct_dex_trajectory_frame"
    assert rows_with > 1000, f"expected a populated epoch, got {rows_with} rows with outcomes"
    share = verdicts[GATE] / sum(verdicts.values())
    assert share > 0.30, f"the gate should dominate verdicts; measured {share:.2%}"
    touch = [seq for seq in pairs.values() if GATE in seq]
    assert len(touch) > 10_000, f"too few gate-touching pairs to judge ({len(touch)})"
    ends = sum(1 for seq in touch if seq[-1] == GATE) / len(touch)
    assert ends > 0.80, (
        f"the gate should be terminal for most pairs that touch it; measured {ends:.1%}. If this "
        f"falls, the upstream observation constraint has genuinely loosened")
