"""RUNUP-FLOOR150 — entry-time run-up caps, as NEW entry arms.

The measured problem these arms exist for
-----------------------------------------
Round 120-20, on the live forward epoch (1,712 positions with a usable pre-entry
window, actual -11,509.67U):

    runup = current price / earliest observed price in the 20 minutes before the
            decision, minus 1

    cap        kept    write-off   U/pos    win rate
    -------------------------------------------------
    <=  5%      442       0.5%     -4.22     10.2%
    <= 10%      571       0.4%     -3.39     17.9%
    <= 15%      678       0.6%     -2.88     18.6%   <- the safe zone ends here
    <= 20%      771       6.0%     -3.76     18.7%   <- write-off rate jumps
    <= 25%      864       8.2%     -4.09     17.9%
    <= 30%      957       9.0%     -3.63     19.5%
    none       1712      24.8%     -6.73     13.9%

The separation is sharp and TOKEN-CLUSTERED SIGNIFICANT in BOTH directions:

    write-off difference (high - low run-up)  +0.322 pp   95% CI [+0.082, +0.565]
    PnL difference      (high - low run-up)  -4.851 U/pos 95% CI [-9.491, -0.055]

and it is not the survival confound: `r(run-up, discovery->entry delay) = -0.116`.
It is the SAME quantity as the activity floor's complement, and the two are only
partially overlapping - the worst quadrant (already run up AND quiet) carries a
**64.1% write-off rate at -12.48 U/pos**, while the best carries **0.3%**.

Why the 20-minute window
------------------------
The lifetime run-up (from the token's very first observed price) separates about
equally, but it is NOT free: `history` in the acceptance loop
(`store.py:27614`) holds only the token's observer frames from the **last 20
minutes** (`LIMIT 80`), so a lifetime figure would need an extra per-token lookup.
The 20-minute definition is computed from `history[0]["price"]` - already in scope,
zero extra queries - and measures at least as well.

Why a new arm is the right instrument
-------------------------------------
These arms reuse `kind = "merged_multi_setup"` and clone the exit contract of
`alpha149_merged_multi_setup_fast_v1` exactly: same kind, same hold, same stop, same
trail, same notional. `runup_floor150_r15_v1` differs from that control in **one**
respect (the run-up cap); `runup_floor150_r15a30_v1` states the conjunction the
quadrant analysis actually favours. Nothing here modifies, replaces or retunes an
existing arm.

Honest limits
-------------
The level is chosen in-sample, the effect is concentrated (37 tokens on this epoch),
and **the kept book still loses money** (-2.88 U/pos). The conjunction is the best
configuration measured but it is a conjunction, not a one-factor result. These are
FORWARD experiments to be judged only on data observed after their activation
frontier.

Missing evidence never admits: with no before-window frame the run-up is unknown and
the arm must not enter.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

VERSION = "runup_floor150/v1"

PARENT_ARM = "alpha149_merged_multi_setup_fast_v1"
PARENT_KIND = "merged_multi_setup"
HOLD_MINUTES = 15

# The top of the measured safe zone: 0.6% write-off at <=15%, 6.0% at <=20%.
RUNUP_CAP_PCT = 15.0
# The activity floor from ACTIVITY-FLOOR150, reused for the conjunction arm.
MIN_TRADES = 30.0

NAMES = {
    "runup_floor150_r15_v1": "入场涨幅上限·20分钟≤15%",
    "runup_floor150_r15a30_v1": "入场涨幅≤15% 且 5分钟成交≥30笔",
}

# One factor per arm where possible: r15 is the clean one-factor variant of the control;
# r15a30 is the conjunction the quadrant analysis favours.
FLOORS: dict[str, dict[str, float]] = {
    "runup_floor150_r15_v1": {"max_runup_pct": RUNUP_CAP_PCT},
    "runup_floor150_r15a30_v1": {"max_runup_pct": RUNUP_CAP_PCT, "min_trades": MIN_TRADES},
}

ARMS: dict[str, tuple[str, str, int]] = {
    arm: (PARENT_KIND, NAMES[arm], HOLD_MINUTES) for arm in FLOORS
}

# The control's exit contract, copied verbatim so the entry filter is the only difference.
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
    "runup_floor150_r15_v1": (
        "入场涨幅上限臂·入场价相对「决策前20分钟内最早一次观测价」涨幅≤15%。"
        "依据：本账期 1,712 个仓位的写下线率在该阈值处发生跳变——≤15% 时 0.6%，"
        "≤20% 时升到 6.0%，不设限则 24.8%；且该分离在按代币聚类的自助法下双向显著"
        "（写下线率差 +0.322pp，CI [+0.082,+0.565]；每仓收益差 −4.851U，CI [−9.491,−0.055]）。"
        "与代币存活期混淆无关（与发现→入场延迟相关系数仅 −0.116）。"
        "本臂与 alpha149_merged_multi_setup_fast_v1 同 kind、同持仓、同止损/追踪/名义仓位，"
        "**唯一差别就是这道涨幅上限**。20分钟窗口是因为 history 本身就只含最近20分钟，"
        "无需任何额外查询。缺失前窗观测一律不入场；触发不等于成交，非已证Alpha。"),
    "runup_floor150_r15a30_v1": (
        "入场涨幅≤15% 且 5分钟成交≥30笔（双条件联合臂）。依据：两个条件只部分重叠，"
        "「已上涨 且 冷清」象限的写下线率高达 64.1%、−12.48U/仓，而「未上涨 且 活跃」象限仅 0.3%。"
        "本臂是实测中期望值最好的组合，但它是联合条件、不是单因子对照，"
        "因此与 r15 臂配对使用才能分离各自的贡献。缺失数据一律不入场；非已证Alpha。"),
}


def _entry_filter(arm: str) -> dict[str, Any]:
    return {
        "direction": arm,
        "max_concurrent_positions": 2,
        "single_token_lifetime_entry": True,
        # Declared on the arm as well so the filter is visible in the policy body itself and to
        # the explainability surface, not only in the acceptance loop that enforces it.
        "entry_floor": {k: v for k, v in FLOORS[arm].items() if k != "min_trades"},
        **({"activity_floor": {"min_trades": FLOORS[arm]["min_trades"]}}
           if "min_trades" in FLOORS[arm] else {}),
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


def runup_pct(snapshot: Any, history: Any) -> float | None:
    """The pool's run-up over the observed before-window, in percent, or None if unknown.

    `history` is the acceptance loop's own ascending list of that token+pair's observer
    frames from the last 20 minutes, so `history[0]` is the earliest frame and this needs
    no extra query. The current price is the snapshot being decided on.
    """
    if not history:
        return None
    try:
        earliest = float(history[0].get("price") or 0.0)
    except (AttributeError, TypeError, ValueError):
        return None
    current = float(getattr(snapshot, "price_usd", None) or 0.0)
    if earliest <= 0 or current <= 0:
        return None
    return (current / earliest - 1.0) * 100.0


def trades_of(snapshot: Any) -> int:
    buys = getattr(snapshot, "buys_5m", None) or 0
    sells = getattr(snapshot, "sells_5m", None) or 0
    return int(buys) + int(sells)


def reject_reason(arm: str, snapshot: Any, history: Any = None) -> str | None:
    """None when the arm may act (including every arm that is not a RUNUP-FLOOR150 arm)."""
    floor = FLOORS.get(str(arm))
    if floor is None:
        return None
    cap = floor.get("max_runup_pct")
    if cap is not None:
        runup = runup_pct(snapshot, history)
        if runup is None:
            return "runup_floor_window_unknown"
        if runup > cap:
            return "runup_floor_exceeded"
    minimum_trades = floor.get("min_trades")
    if minimum_trades is not None and trades_of(snapshot) < minimum_trades:
        return "activity_floor_trades_not_met"
    return None


def allows(arm: str, snapshot: Any, history: Any = None) -> bool:
    """True unless this is one of our arms and the pool fails its entry floor."""
    return reject_reason(arm, snapshot, history) is None


def apply(policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stamp identity and the cloned exit contract onto our own arms only."""
    for policy in policies:
        arm = str(policy.get("arm_id") or "")
        if arm not in ARMS:
            continue
        policy.update(deepcopy(OVERRIDES[arm]))
    return policies


def snapshot() -> dict[str, Any]:
    return dict(
        version=VERSION,
        arms=sorted(ARMS),
        parent_arm=PARENT_ARM,
        parent_kind=PARENT_KIND,
        floors={arm: dict(FLOORS[arm]) for arm in sorted(FLOORS)},
        window="20 minutes, taken from the acceptance loop's own `history` (no extra query)",
        one_factor_only=(
            "runup_floor150_r15_v1 differs from the control in exactly one respect; "
            "runup_floor150_r15a30_v1 is the measured-best conjunction and is paired with it"
        ),
        evidence=(
            "write-off rate jumps from 0.6% at a 15% run-up cap to 6.0% at 20% and 24.8% "
            "uncapped; token-clustered bootstrap is significant both ways (write-off "
            "+0.322pp CI [+0.082,+0.565]; PnL -4.851 U/pos CI [-9.491,-0.055]); not the "
            "survival confound (r=-0.116 with entry delay). CAVEAT: level chosen in-sample, "
            "effect concentrated over 37 tokens, and the kept book STILL LOSES -2.88 U/pos."
        ),
        missing_evidence="never admits (no before-window frame => run-up unknown => no entry)",
        affects="paper_only",
        extra_requests=0,
    )


def merged_specs(specs: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(specs)
    merged.update(ARMS)
    return merged
