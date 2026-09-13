"""Forward-only right-tail recovery arms using only causal DEX observations.

These arms address a measured operational gap: a token can have usable, repeated
DexScreener frames while optional security providers return no usable fields.  The
fallback is deliberately scoped to these Paper arms; it never changes an existing
arm and never treats missing data as proof of safety.
"""

from copy import deepcopy


CONTRACT = "righttail-recovery/152-v1"
SAFETY_PROXY = "causal-dex-continuity/152-v1"
SIGNAL_KIND = "quiet_acceleration152"
CONTROL_ARM = "alpha152_quiet_acceleration_control_v1"
WIDE_ARM = "alpha152_quiet_acceleration_wide_v1"
ARMS = (CONTROL_ARM, WIDE_ARM)


def signal(flags: dict) -> bool:
    """Merge the two existing available-data proxies into one entry predicate."""
    return bool(
        flags.get("trade_activity_growth151")
        or flags.get("buy_pressure_no_breadth151")
    )


def policy(base: dict, arm_id: str) -> dict:
    """Clone one proven-runnable carrier and alter only declared 152 fields."""
    if arm_id not in ARMS:
        raise ValueError("unknown right-tail recovery arm")
    result = deepcopy(base)
    result.update(
        arm_id=arm_id,
        canonical_id=arm_id,
        name=(
            "静默加速152·短持对照"
            if arm_id == CONTROL_ARM
            else "静默加速152·右尾宽持"
        ),
        entry_family=arm_id,
        feature_contract=CONTRACT,
        feature_hypothesis=SIGNAL_KIND,
        paper_safety_proxy=SAFETY_PROXY,
        source_arm_ids=[
            "alpha149_trade_activity_growth_proxy_v1",
            "alpha149_buy_pressure_no_breadth_v1",
        ],
        paired_opportunity_group="righttail_recovery152",
        excess_return_vs_arm=(WIDE_ARM if arm_id == CONTROL_ARM else CONTROL_ARM),
        entry_filter={
            **(base.get("entry_filter") or {}),
            "direction": arm_id,
            "max_concurrent_positions": 2,
            "single_token_lifetime_entry": True,
        },
        decision_eligible=True,
        affects="paper_only",
        no_historical_backfill=True,
        description=(
            "独立前向 Paper：把现有的成交活跃度增长与买盘压力代理合并为一个入场，"
            "要求同一原池的连续新鲜 Dex 帧；收费或受限安全 API 无可用字段时，仅本策略"
            "可用原池身份、流动性、成交活跃度和价格连续性作降级近似。明确危险证据仍拒绝。"
        ),
    )
    if arm_id == CONTROL_ARM:
        result.update(
            max_hold_minutes=30,
            hard_stop_return=-0.20,
            hard_stop_grace_seconds=60,
            hard_stop_confirm_marks=2,
            trailing_activate_return=0.30,
            trailing_drawdown=0.15,
            take_profit=[],
        )
    else:
        result.update(
            max_hold_minutes=180,
            hard_stop_return=-0.50,
            hard_stop_grace_seconds=180,
            hard_stop_confirm_marks=2,
            hard_stop_liquidity_veto_usd=3000.0,
            hard_stop_liquidity_veto_min_buy_share=0.50,
            trailing_activate_return=0.60,
            trailing_drawdown=0.30,
            take_profit=[{"return": 1.0, "fraction_of_remaining": 0.50}],
        )
    for key in (
        "behavior_contract_hash",
        "forward_activation_snapshot_id",
        "forward_started_at",
        "runtime_addition_id",
        "entry_paused",
        "entry_pause_reason",
        "account_lifecycle",
    ):
        result.pop(key, None)
    return result
