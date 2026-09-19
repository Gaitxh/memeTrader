from copy import deepcopy

from memetrader.cohort_experiments import cohort_experiment_policies
from memetrader.store import Store
from memetrader.trajectory144 import ARMS, policies as trajectory_policies
from memetrader import unpaired_trend249 as revision


def parent_policy():
    return next(
        item for item in trajectory_policies(cohort_experiment_policies()[2])
        if item["arm_id"] == revision.PARENT
    )


def test_revision_removes_only_obsolete_pair_contract():
    parent = parent_policy()
    before = deepcopy(parent)
    candidate = revision.policy(parent)
    assert parent == before
    assert candidate["revision_of"] == revision.PARENT
    assert candidate["entry_filter"]["direction"] == revision.ARM
    assert "paired_entry_group" not in candidate
    assert "paired_entry_size" not in candidate
    assert candidate["no_historical_backfill"] is True
    ignored = {
        "arm_id", "canonical_id", "entry_family", "name", "description",
        "revision_of", "source_arm_ids", "entry_filter", "assessment_status",
        "no_historical_backfill", "unpaired_continuation_contract",
        "comparison_semantics",
    }
    assert {k: v for k, v in candidate.items() if k not in ignored} == {
        k: v for k, v in parent.items()
        if k not in ignored and k not in {
            "account_lifecycle", "assessment_evidence", "assessment_note",
            "behavior_contract_hash", "entry_paused", "forward_activation_snapshot_id",
            "forward_started_at", "original_forward_started_at", "runtime_addition_id",
            "stage", "paired_entry_group", "paired_entry_size", "excess_return_vs_arm",
        }
    }


def test_alias_is_same_signal_with_new_identity_and_no_extra_requests():
    source = {
        "decision_key": "source:1",
        "selected": {"token_id": "solana:A", "pair_address": "B"},
        "decision_evidence": {"mode": revision.SIGNAL_PARENT},
    }
    result = revision.alias(source)[revision.ARM]
    assert result["selected"] == source["selected"]
    assert result["decision_key"] == "source:1|" + revision.ARM
    assert result["decision_evidence"]["unpaired_trend249_contract"] == revision.CONTRACT
    assert revision.alias(None) == {}
    assert revision.snapshot()["extra_requests"] == 0


def test_registration_is_append_only_and_idempotent(tmp_path):
    store = Store(tmp_path / "unpaired249.sqlite3", initial_cash_usd=1000)
    try:
        store.activate_chain_meme_trader_funded_period()
        store.register_chain_meme_cohort_experiments()
        version = store.CHAIN_MEME_TRADER_ACTIVE_VERSION
        registration = store._chain_meme_trader_registration(version)
        before = registration["definition_json"]
        assert store.register_chain_meme_unpaired_trend249() == 1
        assert store.register_chain_meme_unpaired_trend249() == 0
        assert store._chain_meme_trader_registration(version)["definition_json"] == before
        row = store.db.execute(
            "SELECT policy_json,activation_snapshot_id FROM "
            "chain_meme_trader_policy_additions WHERE definition_version=? AND arm_id=?",
            (version, revision.ARM),
        ).fetchone()
        assert row is not None
        effective = store._chain_meme_trader_effective_definition(version, before)
        current = next(p for p in effective["policies"] if p["arm_id"] == revision.ARM)
        assert "paired_entry_group" not in current
        assert current["entry_filter"]["direction"] == revision.ARM
    finally:
        store.close()
