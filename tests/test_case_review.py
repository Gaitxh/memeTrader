"""Tests for the case-review tool.

`scripts/case_review.py` answers "the system found this token but never bought it" per token. Three
things decide whether its verdicts are trustworthy, and each gets a test:

  1. RESOLUTION MUST NOT GUESS THE CHAIN. An EVM address does not say whether it is bsc or robinhood,
     and a Solana address must never be case-folded. Resolution is a database lookup.
  2. "NO RECORD" IS NOT "REJECTED". A token with no evaluation row must be reported as
     `never_entry_evaluated`, never as refused -- absence of a record is not evidence a path ran.
  3. THE STAGE NAMES MUST MATCH THE DATA. `blocking_stage` is what the whole review is read from, so
     each boundary is pinned.
"""
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

cr = importlib.import_module("case_review")


def _stage(**over):
    base = {"snapshots": 10, "evaluated": 10, "cohorts": 1, "positions": 1}
    base.update(over)
    return base


def test_resolution_never_guesses_the_chain():
    """An EVM address may be matched case-insensitively; a Solana one must NOT be."""
    exact = {"So1anaCaseSensitive": [{"token_id": "solana:So1anaCaseSensitive"}]}
    folded = {"so1anacasesensitive": [{"token_id": "solana:So1anaCaseSensitive"}]}
    assert cr.resolve(exact, folded, "So1anaCaseSensitive") == exact["So1anaCaseSensitive"]
    # A case-folded Solana string must NOT resolve: only 0x forms are folded.
    assert cr.resolve(exact, folded, "so1anacasesensitive") == []

    evm_exact = {}
    evm_folded = {"0xabc": [{"token_id": "robinhood:0xabc"}]}
    assert cr.resolve(evm_exact, evm_folded, "0xABC") == evm_folded["0xabc"]
    assert cr.resolve(evm_exact, evm_folded, "0xzzz") == []


@pytest.mark.parametrize("stage,expected", [
    ({"snapshots": 0, "evaluated": 0, "cohorts": 0, "positions": 0}, "never_snapshotted"),
    ({"snapshots": 5, "evaluated": 0, "cohorts": 0, "positions": 0}, "never_entry_evaluated"),
    ({"snapshots": 5, "evaluated": 5, "cohorts": 0, "positions": 0}, "evaluated_no_cohort"),
    ({"snapshots": 5, "evaluated": 5, "cohorts": 2, "positions": 0}, "cohort_but_no_position"),
    ({"snapshots": 5, "evaluated": 5, "cohorts": 2, "positions": 3}, "has_position"),
])
def test_blocking_stage_boundaries(stage, expected):
    assert cr.blocking_stage(stage) == expected


def test_no_evaluation_record_is_reported_as_no_record_not_as_refusal():
    """Rule 61: 'not in the data' must not be reported as 'rejected'."""
    assert cr.blocking_stage(_stage(evaluated=0, cohorts=0, positions=0)) == "never_entry_evaluated"


def test_bulk_stages_always_filters_by_definition_version(tmp_path):
    """The evaluations table is indexed only as (definition_version, token_id, ...).

    A query filtered by token_id alone cannot use any index: measured 222 s on 442,920 rows. This test
    asserts the version predicate is present so the tool cannot silently regress into a full scan.
    """
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE token_snapshots(token_id TEXT, observed_at TEXT, provider TEXT);
        CREATE TABLE chain_meme_trader_v6_entry_evaluations(
            definition_version TEXT, token_id TEXT, reason TEXT);
        CREATE TABLE chain_meme_trader_v6_cohorts(
            definition_version TEXT, token_id TEXT);
        CREATE TABLE chain_meme_trader_positions(token_id TEXT);
        CREATE TABLE chain_meme_trader_pool_marks(token_id TEXT, pair_address TEXT);
        """
    )
    conn.execute("INSERT INTO token_snapshots VALUES('solana:A','2026-01-01T00:00:00Z','dexscreener')")
    conn.execute("INSERT INTO chain_meme_trader_v6_entry_evaluations VALUES('v1','solana:A','r1')")
    conn.execute("INSERT INTO chain_meme_trader_v6_entry_evaluations VALUES('OTHER','solana:A','rX')")

    out = cr.bulk_stages(conn, ["solana:A"], ["v1"])
    assert out["solana:A"]["snapshots"] == 1
    # Only the v1 row counts: the OTHER version's row must be excluded by the version predicate.
    assert out["solana:A"]["reasons"] == {"r1": 1}
    assert out["solana:A"]["evaluated"] == 1


@pytest.mark.skipif(not (ROOT / "data" / "memetrader_forward.sqlite3").is_file(),
                    reason="live forward database not present")
def test_live_case_list_resolves_and_none_reached_a_position():
    """The round-91 finding, guarded as a shape rather than a magnitude.

    Every case token that exists in `tokens` must at least have been snapshotted (the user's claim was
    that the system found them), and the run must not crash on the shared 2.4 GB database.
    """
    import sqlite3
    addresses_file = ROOT / "data" / "research" / "diag_round120" / "case_addresses.txt"
    if not addresses_file.is_file():
        pytest.skip("case address list not present")
    conn = sqlite3.connect(f"file:{ROOT / 'data' / 'memetrader_forward.sqlite3'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    exact, folded = cr.load_tokens(conn)
    addresses = [a.strip() for a in addresses_file.read_text(encoding="utf-8").splitlines()
                 if a.strip()]
    found = [a for a in addresses if cr.resolve(exact, folded, a)]
    assert len(found) > 0, "no case address resolved against the live database"
    versions = cr.activated_versions(conn)
    assert versions, "no activated definition version found"
