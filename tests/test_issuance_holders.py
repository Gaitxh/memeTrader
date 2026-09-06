from copy import deepcopy
from datetime import datetime, timezone

from memetrader.issuance_holders import issuance_cohort, issuance_holder_policy
from memetrader.early_observed_buyers import observed_buyer_policy


def test_new_holder_cohort_requires_post_activation_complete_origin_without_relabeling_parent():
    parent = observed_buyer_policy()
    policy = {**issuance_holder_policy(), "activation_evidence_id": 10}
    resolver = {"base_mint": "mint", "quote_mint": "quote", "pool_address": "pool"}
    origin = {"evidence_id": 11, "status": "verified", "create_signature": "signature",
        "observed_at": "2026-09-06T00:00:02Z", "recorded_at": "2026-09-06T00:00:03Z",
        "issuance_holder_snapshot": {"complete": True, "mint": "mint",
            "create_signature": "signature", "slot": 1,
            "block_time": int(datetime(2026,9,6,tzinfo=timezone.utc).timestamp()),
            "owners": [{"owner":"curve", "is_on_curve":False, "amount_raw":900},
                       {"owner":"holder", "is_on_curve":True, "amount_raw":100}]}}
    def cohort(value=origin, chosen=policy):
        return issuance_cohort(value, resolver, policy=chosen,
            activated_at="2026-09-06T00:00:01Z", now="2026-09-06T00:00:04Z")
    result = cohort()
    assert result["buyer_addresses"] == ["holder"] and result["omitted_protocol_owner_count"] == 1
    assert result["coverage"] == "create_transaction_post_state_on_curve_owner_subset"
    assert cohort({**origin, "evidence_id": 10}) is None
    assert cohort({**origin, "observed_at": "2026-09-06T00:00:00Z"}) is None
    assert cohort({**origin, "recorded_at": "2026-09-06T00:00:05Z"}) is None
    for field,value in [("complete",False),("mint","another"),("block_time",origin["issuance_holder_snapshot"]["block_time"]+10)]:
        changed = deepcopy(origin)
        changed["issuance_holder_snapshot"][field] = value
        assert cohort(changed) is None
    assert observed_buyer_policy() == parent
    assert policy["notional_usd"] == 5 and policy["arm_id"] != parent["arm_id"]
