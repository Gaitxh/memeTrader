"""EXIT150 — reachable staged take-profit ladders as NEW exit-carrier arms.

Why this module exists (all figures measured on the live forward epoch
`chain-meme-trader/funding-20260906-v002-final-1000`, window 2026-09-12T18:26Z-20:16Z,
350 positions, using only marks observed strictly after each position opened):

    per-position PEAK economic return
        p10 -7.4%   p25 -1.3%   p50 +22.7%   p75 +32.8%   p90 +34.8%   max +55.0%
        reach +10% econ  227/347 = 65.4%
        reach +20% econ  177/347 = 51.0%
        reach +30% econ  111/347 = 32.0%
        reach +45% econ    4/347 =  1.2%
        reach +60% econ    0/347 =  0.0%
        reach +100% econ   0/347 =  0.0%

    the configured ladder's first tier          +80%  (the one tiered arm uses +100%)
    observed `next_tp_index` on every position  0
    observed `principal_recovered` on every     0
    observed `remaining_quantity_tokens > 0` on closed positions   0

So the first tier sits 1.8x beyond the maximum return the instrument ever produced, the
ladder fired exactly zero times, no profit was ever banked, and total give-back was
4,508.94 USD. A stop at `hard_stop_return = -0.20` economic is a **-13.3% price move**, while
the pools' own 30-second move is p90 9.49% / p95 18.65% - so 44 of 92 hard stops fired within
one minute, inside ordinary noise.

What these arms are
-------------------
They are **exit-carrier arms** in the existing, documented sense: the engine clones the first
frozen entry signal that fires on a pool, so each new arm receives exactly the same
opportunity as whichever entry arm fired first, and only its EXIT contract differs. Every
existing arm therefore acts as the matched control on the same signal, with no extra control
arm and no change to any existing strategy. Nothing here modifies, replaces or retunes an
existing arm.

The three arms vary exactly one thing each, so the comparison is interpretable:

    +---------------------------+----------------+-------------+-----------+---------+
    | arm                       | first tier     | hard stop   | trail     | hold    |
    +---------------------------+----------------+-------------+-----------+---------+
    | exit150_bank15_v1         | +15% / 50%     | -0.35       | .30/.35   | 90 min  |
    | exit150_bank25_v1         | +25% / 50%     | -0.35       | .35/.35   | 90 min  |
    | exit150_widestop_v1       | +15% / 50%     | -0.55       | .30/.45   | 180 min |
    +---------------------------+----------------+-------------+-----------+---------+

`bank15` vs `bank25` isolates where to take the first profit; `bank15` vs `widestop`
isolates how wide the stop should be.

Evidence status: the reachable levels come from the measured distribution above, but the
CHOICE among them is in-sample on that one window. These arms are therefore a forward
experiment to be judged only on data observed after their own activation frontier - never
promoted on the strength of the window that motivated them.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

VERSION = "exit150/v1"

# Measured reachability drives the levels: +15% is inside the 51-65% band, +30% is at the
# 32% quantile, and the last tier sits at the observed maximum so the moonbag is a genuine
# right-tail bet rather than an unreachable target.
REACHABLE_TIERS = (
    {"return": 0.15, "fraction_of_remaining": 0.50},
    {"return": 0.30, "fraction_of_remaining": 0.40},
    {"return": 0.55, "fraction_of_remaining": 0.50},
)
# The remainder (~15% of the original) rides the trailing stop as a moonbag.
LATER_TIERS = (
    {"return": 0.25, "fraction_of_remaining": 0.50},
    {"return": 0.45, "fraction_of_remaining": 0.40},
    {"return": 0.70, "fraction_of_remaining": 0.50},
)

# trajectory_exit stays None on purpose. The market-mark exit branch consults the staged
# `take_profit` ladder directly, whereas the trajectory-exit branch is preempted by the hard
# stop earlier in the same evaluator, so a ladder-based arm must not depend on it.
EXIT_ARMS: dict[str, str] = {
    "exit150_bank15_v1": "exit150_bank15",
    "exit150_bank25_v1": "exit150_bank25",
    "exit150_widestop_v1": "exit150_widestop",
}

KINDS: dict[str, str] = {
    "exit150_bank15": "分批止盈·首档+15%（收益兑现优先）",
    "exit150_bank25": "分批止盈·首档+25%（让利润多跑一段）",
    "exit150_widestop": "分批止盈·首档+15%+超宽止损（抗噪优先）",
}

_COMMON = dict(
    notional_usd=1.0,
    max_concurrent_positions=4,
    trailing_activate_return=0.30,
    trailing_drawdown=0.35,
    max_hold_minutes=90,
    # No trajectory_exit kind: the staged ladder is the primary exit and it must not depend on
    # a branch that the hard stop preempts.
    trajectory_exit=None,
    assessment_status="INSUFFICIENT",
    observer_only=False,
    decision_eligible=True,
    affects="paper_only",
)

OVERRIDES: dict[str, dict[str, Any]] = {
    "exit150_bank15_v1": dict(
        _COMMON,
        name=KINDS["exit150_bank15"],
        take_profit=[dict(tier) for tier in REACHABLE_TIERS],
        hard_stop_return=-0.35,
        description=(
            "EXIT150·首档+15%兑现一半。依据：该账期每个仓位自身的峰值经济收益 p50 +22.7%、"
            "p90 +34.8%、最大 +55.0%，而既有首档止盈是 +80%，命中率 0/350，从未兑现过利润。"
            "本臂只改退出合同，入场信号与既有臂完全相同，因此既有臂即为同信号对照。"
            "1U×4仓，缺失不推断，触发不等于成交。"),
    ),
    "exit150_bank25_v1": dict(
        _COMMON,
        name=KINDS["exit150_bank25"],
        take_profit=[dict(tier) for tier in LATER_TIERS],
        hard_stop_return=-0.35,
        trailing_activate_return=0.35,
        description=(
            "EXIT150·首档+25%，与 bank15 唯一的差别是首档位置，用于判断利润该早兑现还是多跑一段。"
            "1U×4仓，同信号对照，非已证Alpha。"),
    ),
    "exit150_widestop_v1": dict(
        _COMMON,
        name=KINDS["exit150_widestop"],
        take_profit=[dict(tier) for tier in REACHABLE_TIERS],
        # -0.55 economic is roughly a -51% price move: far outside the measured p95 30-second
        # move of 18.65%, so a normal wick cannot stop the position out.
        hard_stop_return=-0.55,
        trailing_drawdown=0.45,
        max_hold_minutes=180,
        description=(
            "EXIT150·首档+15% 但止损放宽到 -0.55（约 -51% 价格），与 bank15 唯一的差别是止损宽度；"
            "既有 -0.20 相当于 -13.3% 价格，而池子自身 30 秒波动 p90 9.49%/p95 18.65%，"
            "实测 92 次硬止损中 44 次在 1 分钟内触发。1U×4仓，同信号对照。"),
    ),
}


def installment_cap() -> float:
    """Total notional across the three arms, for the caller's budget accounting."""
    return float(_COMMON["notional_usd"]) * len(EXIT_ARMS)


def apply(policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stamp EXIT150 identity and the exit contract onto its own arms only.

    Any policy whose arm_id is not an EXIT150 arm is returned untouched, so this can be
    called from the shared policy builder without affecting another module's arms.
    """
    for policy in policies:
        arm = str(policy.get("arm_id") or "")
        if arm not in EXIT_ARMS:
            continue
        # `name` lives in the override because `alpha149.adjust` applies OVERRIDES last, after
        # it has already assigned the generic "ALPHA149·<arm>" label.
        #
        # `feature_contract` is deliberately NOT set here. The registered exit carriers use
        # `alpha149/v1`, which is what the shared feature routing keys on; relabelling it to an
        # EXIT150 contract would risk routing the arm away from the features it reads.
        policy["name"] = KINDS.get(EXIT_ARMS[arm], arm)
        policy["exposure_contract"] = "exit_carrier_same_signal_as_first_firing_arm/v1"
        policy.update(deepcopy(OVERRIDES[arm]))
    return policies


def snapshot() -> dict[str, Any]:
    return dict(
        version=VERSION,
        arms=sorted(EXIT_ARMS),
        carrier_contract="clones the first frozen entry signal on the pool",
        exit_contracts={arm: dict(OVERRIDES[arm]) for arm in sorted(EXIT_ARMS)},
        evidence=(
            "levels chosen from the measured per-position peak economic return distribution "
            "(p50 +22.7%, p90 +34.8%, max +55.0%; +20% reached by 51.0%) against a configured "
            "first tier of +80% that fired 0 times in 350 positions; the CHOICE among them is "
            "in-sample and must be judged only on post-activation forward data"
        ),
        affects="paper_only",
        extra_requests=0,
    )


def merged_specs(specs: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of `specs` with the EXIT150 arms added under their own kind names."""
    merged = dict(specs)
    for arm, kind in EXIT_ARMS.items():
        merged[arm] = (kind, KINDS[kind], int(OVERRIDES[arm]["max_hold_minutes"]))
    return merged
