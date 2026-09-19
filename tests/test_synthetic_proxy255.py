from datetime import datetime, timezone

from memetrader.cohort_experiments import recovered_signal_aliases
from memetrader.synthetic_proxy255 import ARM, CONTRACT, PARENT, alias, policy


def parent_policy():
    return {
        "arm_id": PARENT, "canonical_id": PARENT, "entry_family": PARENT,
        "notional_usd": 1.0, "max_hold_minutes": 5.0,
        "absolute_max_hold_seconds": 300, "hard_stop_return": -0.2,
        "requires_exact_pool_sell_simulation": True,
        "paired_opportunity_group": PARENT,
        "entry_filter": {"direction": PARENT, "chains": ["bsc"],
                         "max_concurrent_positions": 1},
    }


def test_policy_changes_only_the_declared_safety_evidence_contract():
    parent = parent_policy()
    revised = policy(parent)
    assert parent["requires_exact_pool_sell_simulation"] is True
    assert revised["arm_id"] == ARM
    assert revised["revision_of"] == PARENT
    assert revised["paper_safety_proxy"] == "causal-dex-continuity/152-v1"
    assert "requires_exact_pool_sell_simulation" not in revised
    for key in ("notional_usd", "max_hold_minutes", "absolute_max_hold_seconds",
                "hard_stop_return"):
        assert revised[key] == parent[key]


def test_alias_reuses_frozen_parent_clocks_and_has_independent_receipt():
    at = datetime(2026, 9, 19, tzinfo=timezone.utc).isoformat()
    source = {"decision_key": "synthetic:1", "episode_id": "synthetic:1",
              "observed_at": at, "recorded_at": at,
              "decision_evidence": {"phase": "SYNTHETIC_LPI_BUILDING"}}
    result = alias(source)[ARM]
    assert result["decision_key"] == "synthetic:1|" + ARM
    assert result["observed_at"] == source["observed_at"]
    assert result["recorded_at"] == source["recorded_at"]
    assert result["decision_evidence"]["synthetic_proxy_contract"] == CONTRACT
    assert result["decision_evidence"]["extra_market_requests"] == 0
    assert ARM in recovered_signal_aliases({PARENT: source})
