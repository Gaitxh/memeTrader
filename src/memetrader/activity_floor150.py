"""ACTIVITY-FLOOR150 — entry-time pool-activity floors, as NEW entry arms.

The measured problem these arms exist for
-----------------------------------------
Round 120-18, on the live forward epoch (1,035 closed positions, 23 tokens,
actual -8,990.05U):

    entry activity floor      positions kept    write-off rate
    ---------------------------------------------------------
    none                            1035             34.8%
    trades >= 10                     944             36.2%
    trades >= 30                     571              6.0%
    vol5   >= 3,000                  516             14.1%
    vol5   >= 10,000                 404              8.4%

where `trades = buys_5m + sells_5m` and `vol5 = volume_5m_usd` **on the entry
snapshot itself**. Token-clustered bootstrap on the per-position gain from
`trades >= 30`: +9.73 U/pos, 95% CI [+3.93, +14.17] — excludes zero.

Chain-stratified, the mechanism is a BSC death filter:

    bsc,    < 30 trades    404 positions   78.6% write-off   -15.39 U/pos
    bsc,    >= 30 trades   132 positions    7.6% write-off    -4.75 U/pos
    solana, < 30 trades     55 positions    0.0% write-off    -2.67 U/pos
    solana, >= 30 trades   352 positions    6.8% write-off    -4.43 U/pos

Those 404 low-activity BSC positions alone are about -6,218U, i.e. **69.2% of the
whole epoch loss**, in one identifiable, filterable population. The floor helps
BOTH chains (removing a set that loses -2.67U/pos still improves the book).

Why a new arm is the right instrument
-------------------------------------
The system already carries 296 numeric entry gates, but their floors sit at
`min_trades` 4-12 and `min_volume` 300-1200 (consumed at
`revision_evidence_extensions.py:279`) — exactly the band where the sweep shows
they do nothing (`trades >= 10` is worth +552U of a possible +6,528U). Those
gates also live on `evidence_extension_l0` arms that hold 1-2 positions each,
while the 1,409 positions actually held come from 154 `isolated_cohort_observer`
arms whose entire `entry_filter` is `{direction, max_concurrent_positions,
single_token_lifetime_entry}` — no activity gate at all.

So these arms reuse `kind = "merged_multi_setup"` and clone the exit contract of
`alpha149_merged_multi_setup_fast_v1` exactly: **same kind, same hold, same stop,
same trail, same notional**. The ONLY difference is the entry activity floor,
which is applied by arm id in the shared cohort-acceptance loop. That makes the
parent arm a matched same-signal control and the comparison a clean one-factor
test.

Nothing here modifies, replaces or retunes an existing arm.

Honest limits
-------------
The levels come from the write-off collapse, which is a mechanism, not from the
PnL sweep, which is in-sample. The effect is concentrated: 3 of 24 tokens carry
83% of the round-17 take-profit gain, and the best combined configuration still
lost -506U with P(profitable) = 12.9%. These are FORWARD experiments to be judged
only on data observed after their own activation frontier.

Missing evidence never admits: a snapshot with no activity fields fails the floor
(measured coverage is complete — 0 nulls in 35,349 snapshots — so this is a
safety net, not a common path).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

VERSION = "activity_floor150/v1"

# The arm whose signals and exit contract these arms clone. `merged_multi_setup` is the
# highest-volume generic mechanism on this epoch (6 arms x 123 emits per 374 cohorts), so the
# matched control has both a large sample and an already-characterised verdict.
PARENT_ARM = "alpha149_merged_multi_setup_fast_v1"
PARENT_KIND = "merged_multi_setup"
HOLD_MINUTES = 15

NAMES = {
    "activity_floor150_t30_v1": "入场活动度下限·5分钟成交≥30笔",
    "activity_floor150_v5k_v1": "入场活动度下限·5分钟成交额≥5000U",
}

# One factor per arm so the comparison stays interpretable.
FLOORS: dict[str, dict[str, float]] = {
    "activity_floor150_t30_v1": {"min_trades": 30.0},
    "activity_floor150_v5k_v1": {"min_volume_5m_usd": 5_000.0},
}

# (kind, name, hold) for the shared SPECS table. `kind` is REUSED so these arms fire on
# exactly the same mechanism flags as the control and receive the same frozen signals.
ARMS: dict[str, tuple[str, str, int]] = {
    arm: (PARENT_KIND, NAMES[arm], HOLD_MINUTES) for arm in FLOORS
}

# The control's exit contract, copied verbatim so the entry floor is the only difference.
_EXIT_CONTRACT = dict(
    hard_stop_return=-0.2,
    trailing_activate_return=0.3,
    trailing_drawdown=0.15,
    max_hold_minutes=HOLD_MINUTES,
    take_profit=[],
    trajectory_exit=None,
    notional_usd=2.0,
    entry_match_mode="isolated_cohort_observer",
    entry_gate="cohort_strict_forward_asof",
    entry_contract="strict_forward_asof_v1",
    feature_contract="alpha149/v1",
    feature_hypothesis=PARENT_KIND,
    trajectory_engine="alpha149",
    requires_distinct_trajectory_frame=True,
    require_post_decision_observation=True,
    execution_profile="dexscreener-market-paper/v2-before-after",
    signal_origin_clock="activation_at",
    family="cohort_forward_experiment",
    assessment_status="INSUFFICIENT",
    evidence_status="FORWARD_HYPOTHESIS_NOT_ALPHA",
    fidelity_status="HYPOTHESIS_ONLY",
    observer_only=False,
    decision_eligible=True,
    forward_enabled=True,
    no_historical_backfill=True,
    affects="paper_only",
    source_arm_ids=[],
)

DESCRIPTIONS = {
    "activity_floor150_t30_v1": (
        "活动度下限臂·5分钟成交笔数≥30。依据：本账期把 1,035 个已平仓仓位按入场快照自身的活动度分层，"
        "写下线率从 34.8% 降到 6.0%（≥30笔）；分层看 bsc 中 <30笔的 404 个仓位写下线率 78.6%、"
        "−15.39U/仓，约 −6,218U，占整个账期亏损（−8,990U）的 69.2%。"
        "本臂与 alpha149_merged_multi_setup_fast_v1 同 kind、同持仓时长、同止损/追踪/名义仓位，"
        "**唯一差别就是这道入场活动度下限**，因此父臂即为同信号对照。"
        "缺失活动度数据一律不入场；触发不等于成交，非已证Alpha。"),
    "activity_floor150_v5k_v1": (
        "活动度下限臂·5分钟成交额≥5000U。与 t30 臂唯一的差别是下限口径（成交额而非笔数），"
        "用于判断「活动度」应以笔数还是金额度量。其余合同与 fast 对照臂完全一致。"
        "缺失数据一律不入场；触发不等于成交，非已证Alpha。"),
}


def _entry_filter(arm: str) -> dict[str, Any]:
    return {
        "direction": arm,
        "max_concurrent_positions": 2,
        "single_token_lifetime_entry": True,
        # Declared on the arm as well so the floor is visible in the policy body itself and to
        # the explainability surface, not only in the acceptance loop that enforces it.
        "activity_floor": dict(FLOORS[arm]),
    }


OVERRIDES: dict[str, dict[str, Any]] = {
    arm: dict(
        _EXIT_CONTRACT,
        name=NAMES[arm],
        canonical_id=arm,
        entry_family=arm,
        excess_return_vs_arm=PARENT_ARM,
        description=DESCRIPTIONS[arm],
        entry_filter=_entry_filter(arm),
    )
    for arm in FLOORS
}


def activity(snapshot: Any) -> tuple[int, float]:
    """The pool's own 5-minute activity at this observation.

    Mirrors the shared gate's own quantity (`revision_evidence_extensions.py:278`:
    `trades = last["buys"] + last["sells"]`) so the measurement and the gate agree.
    """
    buys = getattr(snapshot, "buys_5m", None) or 0
    sells = getattr(snapshot, "sells_5m", None) or 0
    volume = getattr(snapshot, "volume_5m_usd", None) or 0.0
    return int(buys) + int(sells), float(volume)


def reject_reason(arm: str, snapshot: Any) -> str | None:
    """None when the arm may act (including every arm that is not an ACTIVITY-FLOOR150 arm)."""
    floor = FLOORS.get(str(arm))
    if floor is None:
        return None
    trades, volume = activity(snapshot)
    minimum_trades = floor.get("min_trades")
    if minimum_trades is not None and trades < minimum_trades:
        return "activity_floor_trades_not_met"
    minimum_volume = floor.get("min_volume_5m_usd")
    if minimum_volume is not None and volume < minimum_volume:
        return "activity_floor_volume_not_met"
    return None


def allows(arm: str, snapshot: Any) -> bool:
    """True unless this is one of our arms and the pool is too quiet to enter."""
    return reject_reason(arm, snapshot) is None


def apply(policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stamp identity and the cloned exit contract onto our own arms only.

    Every other policy is returned untouched, so this can be called from the shared
    policy builder without affecting another module's arms.
    """
    for policy in policies:
        arm = str(policy.get("arm_id") or "")
        if arm not in ARMS:
            continue
        # `name` lives in the override because `alpha149.adjust` applies OVERRIDES last, after
        # it has already assigned the generic label.
        policy.update(deepcopy(OVERRIDES[arm]))
    return policies


def snapshot() -> dict[str, Any]:
    return dict(
        version=VERSION,
        arms=sorted(ARMS),
        parent_arm=PARENT_ARM,
        parent_kind=PARENT_KIND,
        floors={arm: dict(FLOORS[arm]) for arm in sorted(FLOORS)},
        one_factor_only=(
            "same kind, same hold, same stop/trail/notional as the parent; the entry activity "
            "floor is the only difference, so the parent is the matched same-signal control"
        ),
        evidence=(
            "write-off rate falls 34.8% -> 6.0% at trades >= 30 on 1,035 closed positions; "
            "token-clustered bootstrap +9.73 U/pos, 95% CI [+3.93, +14.17]; chain-stratified "
            "the 404 BSC positions below the floor carry a 78.6% write-off rate at -15.39 U/pos "
            "= 69.2% of the -8,990U epoch loss. CAVEAT: levels chosen in-sample from the "
            "mechanism, the effect is concentrated in a few tokens, and forward data only."
        ),
        missing_evidence="never admits (a snapshot without activity fields fails the floor)",
        affects="paper_only",
        extra_requests=0,
    )


def merged_specs(specs: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of `specs` with the ACTIVITY-FLOOR150 arms added."""
    merged = dict(specs)
    merged.update(ARMS)
    return merged
