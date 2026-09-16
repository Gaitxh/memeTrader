from scripts.audit_strategy_inventory204 import summarize


def test_summary_preserves_current_and_historical_units_without_arm_dump():
    value = {
        "historical_versions": [{"definition_version": "old"}],
        "current_policy_count": 2,
        "distinct_effective_behavior_hashes": 1,
        "duplicate_behavior_groups": [["a", "b"]],
        "arms": [{"arm_id": "a"}, {"arm_id": "b"}],
    }
    result = summarize(value)
    assert result["historical_versions"] == [{"definition_version": "old"}]
    assert result["current_policy_count"] == 2
    assert result["duplicate_behavior_group_count"] == 1
    assert "arms" not in result
