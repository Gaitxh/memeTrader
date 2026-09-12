"""EXIT-LADDER150 — a CLEAN single-factor dose-response on the first take-profit level.

Why another exit module exists
------------------------------
Round 120-57 measured the first same-frontier paired forward result of this epoch:

    exit150_full15_v1  vs  exit150_full25_v1   (both registered at frontier 32175)
    22 shared settled cohorts, 14 DIVERGED
    within-cohort difference (full25 - full15) = -7.124U/pos
    token-clustered 90% CI [-12.942, -1.661]   (excludes zero)

and then found that the pair is NOT a single-factor comparison: `full25` also raises
`trailing_activate_return` from the 0.30 base to 0.35 (see `exits150.py`, where BOTH +25% arms do
this). So that -7.124U/pos cannot be attributed to the take-profit level, and the fleet has no
clean estimate of the level's effect at all.

Mechanism, measured in the same round (so the choice of levels here is not arbitrary): in all 14 of
those diverged cohorts the position's own peak economic return never reached +25%, let alone +35%.
The five dominant ones peaked at -7.7%, 15.5%, 16.5%, 17.1% and 18.4% - so full25's +35% trailing
activation was UNREACHABLE and cannot be their cause, while full15's +15% tier was reachable in four
of the five. The operative difference was the tier: at +15% the position banks and leaves, at +25%
it does not fire and the pool later dies (write-off, about -20U).

What these arms are
-------------------
Four exit-carrier arms in the existing, documented sense: the engine clones the first frozen entry
signal that fires on a pool, so each arm receives exactly the same opportunity as whichever entry
arm fired first, and only its EXIT contract differs. Every existing arm is therefore a matched
same-signal control and NO existing arm is modified, retuned or replaced.

They differ from each other in EXACTLY ONE FIELD - the first tier's `return`:

    +---------------------------+-------------+-----------+--------+---------+--------+
    | arm                       | first tier  | capture   | stop   | trail   | hold   |
    +---------------------------+-------------+-----------+--------+---------+--------+
    | exit_ladder150_t10_v1     | +10%        | 100%      | -0.35  | .30/.35 | 90 min |
    | exit_ladder150_t15_v1     | +15%        | 100%      | -0.35  | .30/.35 | 90 min |
    | exit_ladder150_t20_v1     | +20%        | 100%      | -0.35  | .30/.35 | 90 min |
    | exit_ladder150_t25_v1     | +25%        | 100%      | -0.35  | .30/.35 | 90 min |
    +---------------------------+-------------+-----------+--------+---------+--------+

`trailing_activate_return` is pinned at the 0.30 base for ALL FOUR on purpose. That single pin is
the whole reason this module exists: it is the field that confounded the deployed pair, and holding
it fixed is what makes a difference between two of these arms attributable to the level.

All four register at the same frontier, because round 120-57 measured that same-frontier pairs
accumulate DIVERGED cohorts about an order of magnitude faster than cross-frontier ones (14 and 17
diverged for the same-frontier pairs, against 4 and 3 for the pairs that joined at different
frontiers). Two variants of one hypothesis belong at one frontier.

What this is NOT
----------------
This is NOT a search for the best level to promote. The stated purpose is to measure the SHAPE of
the curve - whether the level is monotone, flat, or peaked - on data observed strictly after these
arms' own activation frontier. All four levels get equal footing; none is a favoured candidate.
The in-sample replay in round 120-53 (with the corrected `0.96*R - 1` kernel) put +10% at
+15,501.9U, +15% at +14,190.2U, +20% at +11,738.9U and +30% at +7,069.8U, i.e. monotonically
decreasing in the level - and because that is in-sample on one window it is the HYPOTHESIS these
arms test, never the reason to promote a level. Choosing a winner from that table would be exactly
the round-26 selection trap.

Honest limits
-------------
`exit_ladder150_t15_v1` is behaviourally identical to the already-deployed `exit150_full15_v1`
(same tier, same stop, same trailing, same hold). It is included so the curve is internally
consistent - four points read under one contract and one frontier - and its duplication is stated
rather than hidden. The pair (`exit150_full15_v1`, `exit_ladder150_t15_v1`) also differs by
frontier, so any difference between those two is a frontier effect and must NOT be read as a
contract effect.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

VERSION = "exit-ladder150/v1"

# The one field that varies. Chosen to span the region the measured reach distribution occupies
# (+10% is reached by ~65% of positions, +20% by ~51%, +30% by ~32%) so the curve has resolution
# where the mass is, and to bracket the two deployed levels (+15%, +25%).
LEVELS: dict[str, float] = {
    "exit_ladder150_t10_v1": 0.10,
    "exit_ladder150_t15_v1": 0.15,
    "exit_ladder150_t20_v1": 0.20,
    "exit_ladder150_t25_v1": 0.25,
}

NAMES = {
    "exit_ladder150_t10_v1": "退出档位剂量组·+10%全清",
    "exit_ladder150_t15_v1": "退出档位剂量组·+15%全清",
    "exit_ladder150_t20_v1": "退出档位剂量组·+20%全清",
    "exit_ladder150_t25_v1": "退出档位剂量组·+25%全清",
}

EXIT_ARMS: dict[str, str] = {arm: arm for arm in LEVELS}

# Everything except the tier level is held fixed at the deployed full-capture contract, and the
# trailing activation is pinned at the 0.30 base - the field that confounded full15 vs full25.
_COMMON = dict(
    notional_usd=1.0,
    max_concurrent_positions=4,
    trailing_activate_return=0.30,
    trailing_drawdown=0.35,
    max_hold_minutes=90,
    hard_stop_return=-0.35,
    trajectory_exit=None,
    assessment_status="INSUFFICIENT",
    observer_only=False,
    decision_eligible=True,
    affects="paper_only",
)


def _description(arm: str) -> str:
    level = LEVELS[arm]
    return (
        f"EXIT-LADDER150·首档 +{level*100:.0f}% 一次性全清。"
        "本模块的作用是给出一个**只差一个字段**的止盈档位剂量-反应曲线。"
        "起因（第 120-57 轮实测）：已部署的 full15/full25 同前沿配对虽有 22 个共享、14 个分歧 cohort、"
        "组内差 −7.124U/仓（CI [−12.942,−1.661]），但两者**不只差档位**——两个 +25% 臂都把追踪激活"
        "从 0.30 抬到 0.35，因此那个数字无法归因于档位。本模块把追踪激活钉死在 0.30，"
        "四个臂之间**只有首档 return 不同**，所以差值可以归因于档位。"
        "机制依据：那 14 个分歧 cohort 的峰值经济收益**全部未达 +25%**（五个主要的是 −7.7%、15.5%、"
        "16.5%、17.1%、18.4%），所以 +35% 的追踪激活在那批仓位上根本不可达，而 +15% 档位在其中四个上可达。"
        "**本臂不是被择优推广的候选**，目的是测量曲线的形状（单调/平坦/有峰）；"
        "四个档位地位相同。第 120-53 轮用正确内核重放得到的单调递减"
        "（+10% +15,501.9U、+15% +14,190.2U、+20% +11,738.9U、+30% +7,069.8U）"
        "是**待检验的假设**，不是推广理由——按同一账期的重放挑档位正是第 26 轮的选择陷阱。"
        "1U×4仓，同信号对照，缺失不推断，触发不等于成交，非已证Alpha。"
    )


OVERRIDES: dict[str, dict[str, Any]] = {
    arm: dict(
        _COMMON,
        name=NAMES[arm],
        canonical_id=arm,
        entry_family=arm,
        excess_return_vs_arm="alpha149_vol_scaled_exit_v1",
        # THE only difference between the arms in this module.
        take_profit=[{"return": LEVELS[arm], "fraction_of_remaining": 1.00}],
        description=_description(arm),
    )
    for arm in LEVELS
}


def apply(policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stamp this module's identity and exit contract onto its own arms only.

    Any policy whose arm_id is not an EXIT-LADDER150 arm is returned untouched, so this can be
    called from the shared policy builder without affecting another module's arms.
    """
    for policy in policies:
        arm = str(policy.get("arm_id") or "")
        if arm not in EXIT_ARMS:
            continue
        # `name` lives in the override because `alpha149.adjust` applies OVERRIDES last, after it
        # has already assigned the generic "ALPHA149·<arm>" label.
        policy["name"] = NAMES[arm]
        policy["exposure_contract"] = "exit_carrier_same_signal_as_first_firing_arm/v1"
        policy.update(deepcopy(OVERRIDES[arm]))
    return policies


def snapshot() -> dict[str, Any]:
    return dict(
        version=VERSION,
        arms=sorted(EXIT_ARMS),
        carrier_contract="clones the first frozen entry signal on the pool",
        levels={arm: LEVELS[arm] for arm in sorted(LEVELS)},
        one_factor_only="the first tier's `return`; every other field is identical across the four",
        pinned_field=(
            "trailing_activate_return=0.30 for all four - the field that confounded the deployed "
            "full15/full25 pair (round 120-57), which is why this module exists"
        ),
        same_frontier=(
            "all four register together; round 120-57 measured same-frontier pairs accumulating "
            "diverged cohorts about an order of magnitude faster than cross-frontier ones"
        ),
        purpose=(
            "measure the SHAPE of the exit-level curve forward, not to promote a level. All four "
            "levels have equal footing; the round-53 in-sample monotone ordering is the hypothesis"
        ),
        evidence=(
            "round 120-57: same-frontier full15/full25, 22 shared / 14 diverged, -7.124U/pos "
            "CI [-12.942,-1.661], BUT confounded by trailing_activate_return 0.30 vs 0.35; and in "
            "all 14 diverged cohorts the peak econ never reached +25%, so the +35% trailing was "
            "unreachable and the tier was the operative difference"
        ),
        dishonesty_guards=(
            "t15 duplicates the deployed full15's behaviour intentionally, for an internally "
            "consistent curve; the (full15, t15) difference is a FRONTIER effect and must not be "
            "read as a contract effect"
        ),
        affects="paper_only",
        extra_requests=0,
    )


def merged_specs(specs: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of `specs` with this module's arms added under their own kind names."""
    merged = dict(specs)
    for arm in EXIT_ARMS:
        merged[arm] = (arm, NAMES[arm], int(OVERRIDES[arm]["max_hold_minutes"]))
    return merged
