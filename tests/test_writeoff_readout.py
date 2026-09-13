"""Writeoff-readout tests.

`scripts/writeoff_readout.py` examines the liquidity-floor cohort -- the largest loss path in the book
-- and answers one question: was there a moment worth exiting into, and could any deployed rule have
acted on it?

Two things about it are easy to get wrong and both change the conclusion:

  1. THE HIGH'S TIME IS RECOVERED, NOT RECORDED. The engine stores the running high's VALUE but not
     its timestamp, so the readout finds the first mark within 1% of that value. That is a LOWER
     bound on when the high was reached, which makes the measured high-to-writeoff gap an
     UNDER-estimate - i.e. the true window was at least as long. If the tolerance were widened or the
     search allowed to run past the position's close, the gap would be inflated instead.

  2. "COULD A RULE HAVE FIRED" MUST BE ASKED PER ARM. Each arm carries its own
     `trailing_activate_return`. Comparing a peak against a global constant would mis-state the
     coverage gap in either direction, so the readout loads the effective definition and compares
     each position with ITS OWN arm's contract.
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

wor = importlib.import_module("writeoff_readout")


def test_econ_kernel_matches_the_established_form():
    """The deployed kernel from round 69. A readout that silently reverts would look authoritative."""
    assert wor.econ(1.0) == pytest.approx(-0.04)
    assert wor.econ(1.0 / 0.96) == pytest.approx(0.0)
    assert wor.econ(1.25) == pytest.approx(0.20)


def test_percentile_is_bounded_and_ordered():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert wor.percentile(vals, 0.0) == 1.0
    assert wor.percentile(vals, 0.99) == 5.0
    assert wor.percentile(vals, 0.25) <= wor.percentile(vals, 0.75)
    assert wor.percentile([], 0.5) is None


def test_parse_is_total():
    assert wor.parse("2026-01-01T00:00:00Z") is not None
    for bad in (None, "", "nope", 3, {}):
        assert wor.parse(bad) is None


def test_high_tolerance_is_a_narrow_band_below_one():
    """The tolerance defines "reaching the high". It must be just under 1 so the recovered time is a
    LOWER bound: a wider band would find an EARLIER mark and inflate the gap to the write-off."""
    assert 0.9 <= wor.HIGH_TOLERANCE < 1.0, (
        f"HIGH_TOLERANCE={wor.HIGH_TOLERANCE} must sit just below 1.0; the recovered high time is "
        f"documented as a lower bound, and a looser band breaks that claim")


def test_cohort_prefix_matches_the_deployed_reason_string():
    assert wor.WRITEOFF_PREFIX == "dex_pool_liquidity_below_configured_floor"
    # the readout uses LIKE prefix matching, so a trailing '%' is appended by the query, not stored
    assert not wor.WRITEOFF_PREFIX.endswith("%")


def test_default_floor_matches_the_deployed_setting():
    """The floor the readout uses to call a pool ALIVE must be the deployed one (1000 USD), or the
    'pool was healthy at the high' claim would be measured against the wrong threshold."""
    assert wor.DEFAULT_FLOOR == 1000.0


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_writeoff_cohort_exists_and_has_positive_peaks():
    """The live property the round-77 finding rests on: this cohort is large and its peaks are mostly
    POSITIVE, i.e. it is not a set of tokens that never moved.

    If the positive share ever collapses, the cohort's character has changed and the coverage-gap
    reading should be revisited rather than carried forward.
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rows = list(c.execute(
        """select stake_usd, entry_execution_price_usd ex, entry_signal_price_usd en,
                  highest_signal_price_usd hi
           from chain_meme_trader_positions
           where status in ('closed','written_off') and closed_at is not null
             and close_reason like ?""", (wor.WRITEOFF_PREFIX + "%",)))
    if len(rows) < 50:
        pytest.skip("write-off cohort too small to judge")
    peaks = []
    for r in rows:
        try:
            ep = float(r["ex"] or r["en"])
            hi = float(r["hi"])
            if ep > 0 and hi > 0:
                peaks.append(wor.econ(hi / ep))
        except (TypeError, ValueError):
            continue
    assert peaks, "no usable peaks in the write-off cohort"
    share_pos = sum(1 for x in peaks if x > 0) / len(peaks)
    assert share_pos > 0.50, (
        f"only {100*share_pos:.1f}% of write-off positions had a positive peak; if this has fallen, "
        f"the cohort is no longer dominated by positions that rose first")


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_writeoff_evidence_is_retained_and_confirms_a_dust_pool():
    """The round-80 correction, asserted so it cannot silently regress.

    Round 79 concluded write-offs were unauditable because the MARK HISTORY shows no collapse. That
    was reading the wrong table: store.py:34676-34704 performs a POST-CONFIRMATION re-quote and stores
    it as terminal_dust_pool in chain_meme_trader_marks.trigger_evidence_json.

    This asserts (a) the evidence is present for essentially every write-off, (b) the confirmed
    liquidity is far BELOW the floor - the signature of a genuine dust pool rather than a premature
    exit, and (c) the confirming quote was fresh relative to its own observation, i.e. the engine did
    not act on a stale reading. If any of these fails, the write-off path needs re-examination rather
    than being treated as closed.
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rows = list(c.execute(
        """select trigger_evidence_json from chain_meme_trader_marks
           where reason like '%dex_pool_liquidity_below_configured_floor%'"""))
    if len(rows) < 50:
        pytest.skip("too few write-off marks to judge")
    liq, lags, with_ev = [], [], 0
    for r in rows:
        try:
            ev = json.loads(r["trigger_evidence_json"] or "{}")
        except (ValueError, TypeError):
            continue
        td = ev.get("terminal_dust_pool")
        pc = ev.get("post_confirmation")
        src = td if isinstance(td, dict) else (pc if isinstance(pc, dict) else None)
        if src is None:
            continue
        with_ev += 1
        try:
            if src.get("liquidity_usd") is not None:
                liq.append(float(src["liquidity_usd"]))
        except (TypeError, ValueError):
            pass
        o, rec = wor.parse(src.get("observed_at")), wor.parse(src.get("recorded_at"))
        if o and rec:
            lags.append((rec - o).total_seconds())

    share = with_ev / len(rows)
    assert share > 0.90, (
        f"only {100*share:.1f}% of write-off marks carry terminal_dust_pool/post_confirmation; if "
        f"this has fallen, write-offs really are un-evidenced and round 79's reading becomes right")

    assert liq, "no confirmed liquidity values found in the evidence"
    below = sum(1 for x in liq if x < wor.DEFAULT_FLOOR) / len(liq)
    assert below > 0.95, (
        f"only {100*below:.1f}% of confirmed write-offs are below the floor - the mechanism is "
        f"supposed to settle only on a confirmed breach")
    med = wor.percentile(liq, 0.5)
    assert med is not None and med < 0.5 * wor.DEFAULT_FLOOR, (
        f"median confirmed liquidity is {med} - if it ever clusters just under the "
        f"{wor.DEFAULT_FLOOR:.0f} floor, exits are becoming premature rather than dust-driven")

    assert lags, "no confirmation timestamps found"
    over = sum(1 for x in lags if x > 15.0)
    assert over / len(lags) < 0.05, (
        f"{100*over/len(lags):.1f}% of confirmations are older than the 15 s window store.py:34680 "
        f"enforces - the engine would be acting on stale readings")


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_healthy_window_is_minutes_not_seconds():
    """The round-81 property, asserted because the opposite reading is easy and was made once.

    While drafting round 81 I measured 'the LAST healthy mark is ~7 s before the write-off' and wrote
    'the median healthy span is of the order of ten seconds'. The 7 s is the final sliver; the SPAN is
    minutes. The distinction decides the whole conclusion: a seconds-long window means no rule could
    react, a minutes-long one means the information was there and was not acted on.

    This asserts the span is minutes and that the marks inside it are plentiful, so the reading cannot
    silently flip back.
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    marks = {}
    for r in c.execute("""select token_id, observed_at, price_usd, liquidity_usd
                          from chain_meme_trader_market_mark_history
                          where price_usd is not null and price_usd > 0
                          order by token_id, observed_at"""):
        t = wor.parse(r["observed_at"])
        if t is not None:
            marks.setdefault(str(r["token_id"]), []).append(
                (t, float(r["price_usd"]),
                 (float(r["liquidity_usd"]) if r["liquidity_usd"] is not None else None)))
    spans, counts, last_gaps = [], [], []
    for r in c.execute("""select token_id, opened_at, closed_at
                          from chain_meme_trader_positions
                          where status in ('closed','written_off') and closed_at is not null
                            and close_reason like ?""", (wor.WRITEOFF_PREFIX + "%",)):
        op, cl = wor.parse(r["opened_at"]), wor.parse(r["closed_at"])
        if op is None or cl is None:
            continue
        healthy = [x for x in marks.get(str(r["token_id"]), [])
                   if op <= x[0] <= cl and x[2] is not None and x[2] >= wor.DEFAULT_FLOOR]
        if len(healthy) < 3:
            continue
        spans.append((healthy[-1][0] - healthy[0][0]).total_seconds())
        counts.append(len(healthy))
        last_gaps.append((cl - healthy[-1][0]).total_seconds())
    if len(spans) < 50:
        pytest.skip("too few measurable healthy windows")

    med_span = wor.percentile(spans, 0.5)
    med_last = wor.percentile(last_gaps, 0.5)
    med_count = wor.percentile(counts, 0.5)
    assert med_span > 120, (
        f"median healthy span is {med_span:.0f}s - if this ever drops to seconds, no rule could "
        f"react and the round-81 reading ('the information was available') would be wrong")
    assert med_count >= 5, (
        f"median known-liquidity marks in the window is {med_count:.0f}; too few to act on")
    assert med_last < med_span / 5, (
        f"the last-healthy-mark gap ({med_last:.0f}s) should be a small fraction of the span "
        f"({med_span:.0f}s); if the two converge, the distinction round 81 drew has collapsed")


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_activation_comparison_uses_per_arm_contracts():
    """The coverage-gap claim requires per-arm activation levels, and requires that the majority of
    the cohort never reaches its OWN arm's level.

    The assertion is deliberately on the per-arm mechanism being available, plus the direction of the
    result; if the gap ever closes, this fails and the finding should be re-examined.
    """
    c = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    # Resolve the version the POSITIONS belong to, then load THAT registration. An unqualified
    # `limit 1` on the registrations table picks an arbitrary epoch whose definition_json carries no
    # "policies" key, which made this test fail with an empty contract rather than a real signal.
    vrow = c.execute("select definition_version from chain_meme_trader_positions limit 1").fetchone()
    if vrow is None:
        pytest.skip("no positions yet")
    version = vrow["definition_version"]
    row = c.execute("select definition_json from chain_meme_trader_registrations "
                    "where definition_version=?", (version,)).fetchone()
    if row is None:
        pytest.skip(f"no registration row for {version}")
    from memetrader.store import Store
    eff = Store.chain_meme_trader_effective_definition_from_connection(
        c, version, json.loads(row["definition_json"]))
    contract = {str(p.get("arm_id")): p for p in eff.get("policies", [])}
    assert contract, "effective definition returned no policies"
    with_act = [p for p in contract.values() if p.get("trailing_activate_return") is not None]
    assert with_act, "no policy carries trailing_activate_return; the comparison is impossible"

    rows = list(c.execute(
        """select arm_id, stake_usd, entry_execution_price_usd ex, entry_signal_price_usd en,
                  highest_signal_price_usd hi
           from chain_meme_trader_positions
           where status in ('closed','written_off') and closed_at is not null
             and close_reason like ?""", (wor.WRITEOFF_PREFIX + "%",)))
    if len(rows) < 50:
        pytest.skip("write-off cohort too small to judge")
    reached = total = 0
    for r in rows:
        pol = contract.get(str(r["arm_id"]))
        act = (pol or {}).get("trailing_activate_return")
        if act is None:
            continue
        try:
            ep = float(r["ex"] or r["en"])
            hi = float(r["hi"])
            if ep <= 0 or hi <= 0:
                continue
        except (TypeError, ValueError):
            continue
        total += 1
        if wor.econ(hi / ep) >= float(act):
            reached += 1
    if total < 50:
        pytest.skip("too few positions with a known activation level")
    share = reached / total
    assert share < 0.50, (
        f"{100*share:.1f}% of write-off positions reached their own arm's trailing activation; the "
        f"coverage-gap reading assumes most do NOT, so if this has risen the finding has reversed")
