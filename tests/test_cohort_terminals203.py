from scripts.diagnose_cohort_terminals203 import classify


def decision(status="admitted", reason="pattern_next_observation"):
    return {"status": status, "reason": reason}


def test_terminal_classification_keeps_units_and_safety_distinct():
    assert classify([decision()], True, []) == "source_buy_filled"
    assert classify([decision()], False, [
        {"safety_status": "CHECKED_WEAK"},
        {"safety_status": "EXPIRED_SECURITY_OR_NEXT_FRAME"},
    ]) == "weak_sellability_evidence"
    assert classify([decision()], False, [
        {"safety_status": "WAIT_DEX_BUY_ONLY"},
        {"safety_status": "EXPIRED_SECURITY_OR_NEXT_FRAME"},
    ]) == "buy_only_no_sell"
    assert classify([decision()], False, [
        {"safety_status": "CHECKED_UNKNOWN", "assessment": {"allow": False}},
    ]) == "safety_unknown_not_allowed"
    assert classify([decision("rejected", "entry_cash_below_order_size")],
                    False, []) == "no_funded_arm_cash"
    assert classify([], False, []) == "no_arm_decision_or_native_path"
    assert classify([], False, [{"safety_status": "BUY_AUTHORIZED_NATIVE_PROTOCOL"}],
                    positions=1) == "position_without_v6_source_fill"
