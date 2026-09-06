"""Create-transaction holder evidence and a separate bounded Paper experiment.

No requests: reuse verified token_origin and actual swap windows. A post-create
balance owner is not a beneficial owner; delegated/custodial sales are not inferred.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib

from .capital_entry import _time, _evidence_ok
from .early_observed_buyers import observed_buyer_policy, evaluate_observed_buyer_distribution


ARM_ID = "issuance_holder_distribution_5u_v1"


def issuance_holder_policy():
    policy = deepcopy(observed_buyer_policy())
    policy.update(arm_id=ARM_ID, canonical_id=ARM_ID,
        name="发行后持有人·实际派发", entry_family="issuance_holder_distribution",
        capital_exit_kind="issuance_holder_distribution",
        source_arm_ids=["early_observed_buyer_distribution_v1"],
        description="复用精确创建交易封存发行后owner集合，后续本人签名实际SELL派发触发退出；非隐藏控制识别。")
    policy["entry_filter"] = {"direction": "issuance_holder_distribution"}
    policy["capital_exit_policy"]["version"] = "issuance-holder-distribution/v1"
    return policy


def issuance_cohort(origin, resolver, *, policy, activated_at, now):
    """Only use a complete origin first received after this arm's frontier."""
    decision, activated = _time(now), _time(activated_at)
    evidence_id = origin.get("evidence_id")
    frontier = policy.get("activation_evidence_id")
    snapshot = origin.get("issuance_holder_snapshot") or {}
    if (not decision or not activated or not _evidence_ok(origin, decision, activated, fresh=False)
            or type(evidence_id) is not int or type(frontier) is not int or frontier < 0
            or evidence_id <= frontier
            or origin.get("status") != "verified" or snapshot.get("complete") is not True
            or not resolver.get("pool_address") or not resolver.get("quote_mint")
            or snapshot.get("mint") != resolver.get("base_mint")
            or snapshot.get("create_signature") != origin.get("create_signature")):
        return None
    block_time = snapshot.get("block_time")
    if (type(block_time) is not int or block_time < 0
            or block_time > _time(origin["observed_at"]).timestamp()):
        return None
    owners = snapshot.get("owners") or []
    # All proof rows are retained; the trading subset is explicitly on-curve owners.
    tracked = [row["owner"] for row in owners if row.get("is_on_curve") is True
               and int(row.get("amount_raw", 0)) > 0]
    if not 0 < len(tracked) <= 32:
        return None
    cohort_id = hashlib.sha256(
        f"{ARM_ID}:{evidence_id}:{resolver['pool_address']}".encode()).hexdigest()
    return {key: resolver[key] for key in ("pool_address", "base_mint", "quote_mint")} | {
        "cohort_id": cohort_id, "source_evidence_id": evidence_id,
        "sealed_at": origin["recorded_at"], "buyer_addresses": tracked,
        "coverage": "create_transaction_post_state_on_curve_owner_subset",
        "mint_initial_holder_coverage": "exact_create_post_state_not_beneficial_ownership",
        "create_signature": snapshot["create_signature"], "slot": snapshot.get("slot"),
        "birth_at": datetime.fromtimestamp(block_time, timezone.utc).isoformat(),
        "omitted_protocol_owner_count": len(owners) - len(tracked),
    }


def evaluate_issuance_distribution(position, frame, state=None, *, now, policy):
    action, reason, next_state, evidence = evaluate_observed_buyer_distribution(
        position, frame, state, now=now, policy=policy)
    return action, reason, next_state, {**evidence, "strategy": ARM_ID,
        "mint_initial_holder_coverage": "exact_create_post_state_not_beneficial_ownership",
        "sale_matching": "owner_signed_actual_swaps_only_not_delegated_or_custodial"}
