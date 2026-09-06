"""Pure revision-2 rules for selected historical strategy slots.

Callers own registration, persistence, next-frame execution and timestamps.
This module only derives immutable policy metadata and evaluates as-of L0 input.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .capital_exits import (
    HOLD,
    SELL,
    WAIT,
    ExitResult,
    _as_time,
    _begin,
    _number,
    _policy_snapshot,
    _result,
)


INACTIVITY_ARM = "canonical-05005fdaa932d3d0"
FLASH_ARM = "broad_flash_tail_first_mover_v1"
MATURE_ARM = "broad_mature_continuity_control_v1"

ACTIVITY_FLOOR_ARMS = frozenset({
    "canonical-1c2ac45bb5154011",
    "canonical-6c728fb1b79d226a",
    "canonical-4b290f4f2bba4fb4",
    "canonical-a6741f19300d52f1",
    "canonical-cae3a114676b9324",
    "canonical-0006b989b189e0ac",
    "canonical-0356dc612c90a689",
    "canonical-19b9d4d442fde1ab",
    "dex-successor-090-b5ad5642ccff0e2e",
    "dex-successor-112-ea5a51ca3135e1b8",
    "dex-successor-041-4a4be8bd60c050f5",
    "dex-successor-094-c39421bc0ad61a44",
    "dex-successor-123-fdcf73ca24c18fcc",
    "dex-successor-026-25ad46e118f6edc9",
    "dex-successor-101-d1cb0c9edad31cbf",
    "dex-successor-108-e44a1533954c80e5",
    "dex-successor-039-46f730df93b191f3",
    "dex-successor-046-546560b93b10c79c",
    "dex-successor-067-842383c9376853b7",
    "dex-successor-088-b18c9c129af7fbfc",
    "dex-successor-095-c78ed4ffa4877807",
    "dex-successor-118-f336bf0ae10004cd",
    "dex-successor-012-0eea3c62cb7bacc4",
    "dex-successor-032-30d85f39d76f4f18",
    "dex-successor-049-5ce40de1d93304fb",
    "dex-successor-052-62d73d37cb094974",
    "dex-successor-068-85b7ea76ae522727",
    "dex-successor-075-977f322fba28b9bc",
    "dex-successor-119-f3cf5416894220d7",
    "dex-successor-120-f98e117baa206954",
})

ADDITIVE_L0_LOSS_EXIT_ARMS = frozenset({
    "canonical-53316326d5f1f7d5",
    "canonical-8e0e2a5367a26beb",
    "canonical-035ad2cf0cb0f6a5",
    "canonical-1ef2715c090f60fb",
    "canonical-57d44c510448173c",
    "canonical-1d9647200c714796",
    "canonical-24ac3d4a360ab98c",
    "canonical-c9204a1e7a1c45f3",
    "canonical-2390fb342a6e90b6",
    "canonical-0cd0f3c790d85ca5",
    "canonical-0d7caccf76779d74",
    "canonical-195049e27d177b1f",
    "canonical-4a27a58cc5902ea9",
    "canonical-63e62a12e74b6320",
    "canonical-75dadf52fc0cdd9e",
    "canonical-7c7c863ffc06fdf6",
    "canonical-831b37e3aaeaa64d",
    "canonical-a0b46b71b30d8575",
    "canonical-aa5d0c9d6721fb48",
    "canonical-ca8f32cf0d565e07",
    "canonical-ddd57b024d84a00b",
})

CONDITIONAL_RUNNER_ARMS = frozenset({
    "experiment_conditional_runner_candidate_v1",
    "experiment_conditional_runner_control_v1",
})

L0_LOSS_DETERIORATION_POLICY = {
    "version": "l0-loss-deterioration/v1",
    "minimum_hold_seconds": 60.0,
    "minimum_bad_frames": 2,
    "minimum_frame_span_seconds": 5.0,
    "maximum_frame_age_seconds": 30.0,
}

_REVISION_METADATA = {
    INACTIVITY_ARM: {
        "reason": "有效样本中池流动性核销占主导，零活跃退出没有覆盖连续池衰退",
        "changes": [
            "保留原入场和既有退出",
            "持有至少60秒后，以基线加两个连续原池L0恶化帧触发下一帧退出",
        ],
        "basis": "79个有效生命周期中41个流动性核销，合计-820 USDC",
    },
    FLASH_ARM: {
        "reason": "高成交笔数配合成交额上限会纳入经济规模很小的短时爆发",
        "changes": [
            "删除5分钟成交额低于1000U的上限",
            "增加5分钟成交额至少200U，保留原全量主通道和既有下一帧成交",
        ],
        "basis": "188次硬止损合计-2216.27 USDC，同时保留41次右尾止盈的入场方向",
    },
    MATURE_ARM: {
        "reason": "此前55分钟多于2笔成交仅证明存在性，不足以证明成熟延续",
        "changes": [
            "保留5至15分钟池龄和prior55大于2的机会起点",
            "增加两个相隔15至90秒且价格/流动性不退、当前有成交的确认帧",
        ],
        "basis": "有效胜率约7.1%，156次最长持有退出和50次硬止损均为净亏损",
    },
}

_ZERO_INPUT_REVISIONS = {
    "experiment_quiet_reawakening_candidate_v1": {
        "reason": "超过10小时零BUY；连续600秒八帧静默要求与自然轮换观察覆盖不匹配",
        "changes": ["改为三帧且至少120秒的已观察静默基线", "保留6小时池龄、成交额、价格和流动性复苏确认"],
        "basis": "最近4000次观察中382次条件未满足、115次等待独立序列且0次READY",
    },
    "experiment_narrative_candidate_v1": {
        "reason": "超过10小时零BUY；没有严格身份匹配的双独立来源narrative证据",
        "changes": ["不放宽来源或身份合同", "新资金期继续记录原始事件漏斗"],
        "basis": "最近有L0输入的504次观察全部awaiting_narrative_evidence",
    },
    "experiment_narrative_control_v1": {
        "reason": "超过10小时零BUY；与候选共享的narrative机会没有出现",
        "changes": ["维持同机会对照", "不得让control脱离narrative事件单独买入"],
        "basis": "最近有L0输入的504次观察全部awaiting_narrative_evidence",
    },
    "finite_capital_ranker_v1": {
        "reason": "超过10小时零BUY；同轮完整actual-flow横截面没有达到ranker输入合同",
        "changes": ["不降低身份和as-of要求", "接入已有自然批次的有界完整横截面后再排名"],
        "basis": "最近有L0输入的504次观察全部wait_ranker_asof_candidates",
    },
    "market_regime_throttle_v1": {
        "reason": "超过10小时零BUY；同一横截面regime未产生可用provenance",
        "changes": ["不凭单token代理全市场状态", "复用ranker的有界as-of横截面"],
        "basis": "最近有L0输入的504次观察全部wait_regime_provenance",
    },
    "competing_risk_v1": {
        "reason": "超过10小时零BUY；已有封存模型但所有成熟帧都被普通亏损优势否决",
        "changes": ["保留death概率否决", "普通亏损不再单独否决，改由一个独立L0不退确认帧约束"],
        "basis": "412次competing_risk_hazard_preferred，另92次等待bin成熟，0次READY",
    },
    "duration_competing_risk_v1": {
        "reason": "超过10小时零BUY；已有封存时长模型但所有成熟bin均未满足利润大于全部竞态之和",
        "changes": ["保留writeoff和观察缺口联合风险否决", "普通亏损由独立L0不退确认帧约束"],
        "basis": "359次duration_loss_incidence_preferred，另145次等待bin成熟，0次READY",
    },
    "direct_lp_float_constrained_v1": {
        "reason": "超过10小时零BUY；可用观察中缺完整NORMAL_DIRECT surface/permission或证据已过期",
        "changes": ["不放宽PDA、mint或pool identity", "仅修自然surface证据到observer的接线"],
        "basis": "422次缺as-of/permission、46次过期、36次非NORMAL_DIRECT",
    },
    "direct_lp_amount_specific_confirmed_v1": {
        "reason": "超过10小时零BUY；上游Direct LP身份门尚未通过，因此未进入amount-specific preflight",
        "changes": ["保留完整双向preflight", "只在同一现有surface和actual-flow证据齐全时低频请求"],
        "basis": "阻断分布与Direct LP parent相同且最近证据无preflight完成记录",
    },
    "authoritative_event_shock_v1": {
        "reason": "超过10小时零BUY；没有严格first-party exact-contract事件",
        "changes": ["不把营销或当前网页代理为官方事件", "保留事件到下一帧的因果边界"],
        "basis": "最近有L0输入的504次观察全部wait_authoritative_event",
    },
    "official_event_actual_flow_v1": {
        "reason": "超过10小时零BUY；父级官方事件未出现，尚未到事件后资金确认",
        "changes": ["不移除官方事件父门", "事件出现后复用完整actual-flow窗口"],
        "basis": "最近有L0输入的504次观察全部wait_authoritative_event",
    },
    "event_reawakening_v1": {
        "reason": "超过10小时零BUY；自然观察没有同时满足正actual-flow与有效广度",
        "changes": ["保留官方事件和成熟池约束", "将flow缺失与flow非正分开记录后再决定规则"],
        "basis": "最近有L0输入的504次观察全部awaiting_positive_actual_flow_and_breadth",
    },
    "surface_lifecycle_pipeline_v1": {
        "reason": "超过10小时零BUY；surface分流前的正actual-flow与广度父门未通过",
        "changes": ["保留精确surface身份", "允许既有自然surface先分类并分别报告flow缺失，不制造BUY"],
        "basis": "最近有L0输入的504次观察全部awaiting_positive_actual_flow_and_breadth",
    },
    "no_ca_event_flow_leader_v1": {
        "reason": "超过10小时零BUY；没有封存的无CA候选资金leader证据",
        "changes": ["保留authoritative_ca=False与actual-flow", "修复自然候选rank evidence生产后再下一帧入场"],
        "basis": "最近有L0输入的504次观察全部awaiting_frozen_candidates_actual_flow_and_next_frame",
    },
    "migration_amount_rate_absorption_v1": {
        "reason": "超过10小时零BUY；多数观察不是严格前向Solana migration identity，少数缺完整资金窗",
        "changes": ["先按链和migration receipt路由观察", "保留两个相邻完整金额窗与flush/absorption合同"],
        "basis": "344次identity missing、75次fact非严格前向、49次flow缺失、17次window无效",
    },
}

_REVISION_METADATA.update({
    arm_id: _ZERO_INPUT_REVISIONS[arm_id]
    for arm_id in (
        "experiment_quiet_reawakening_candidate_v1",
        "competing_risk_v1",
        "duration_competing_risk_v1",
    )
})

_ACTIVITY_FLOOR_METADATA = {
    "reason": "亏损组在原入场框架下接受了5分钟成交活跃度不足的机会",
    "changes": ["保留原入场覆盖和退出", "要求5分钟至少3笔成交且成交额至少200U"],
    "basis": "现有L0已提供成交笔数与成交额；不增加RPC或转入isolated observer",
}
_ADDITIVE_L0_EXIT_METADATA = {
    "reason": "既有退出未覆盖持有60秒后连续可观察的价格与流动性同步恶化",
    "changes": ["保持原入场及原退出", "叠加两帧L0亏损恶化的下一帧退出"],
    "basis": "只使用持仓原池已有L0帧，不以污染经济结果证明策略优劣",
}
_CONDITIONAL_RUNNER_METADATA = {
    "reason": "原规则在单帧age<=900且成交数>=3时立即READY，未执行声明中的时间确认",
    "changes": ["保持isolated pattern observer", "候选与对照共享15至90秒两帧确认并同机会入场"],
    "basis": "当前forward_patterns conditional_runner分支是单帧broad_launch_pattern",
}


def revision_spec(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copied revision-2 policy, or an unchanged copy for other arms."""
    revised = copy.deepcopy(dict(policy))
    arm_id = str(revised.get("arm_id") or "")
    metadata = _REVISION_METADATA.get(arm_id)
    if arm_id in ACTIVITY_FLOOR_ARMS:
        metadata = _ACTIVITY_FLOOR_METADATA
    elif arm_id in ADDITIVE_L0_LOSS_EXIT_ARMS:
        metadata = _ADDITIVE_L0_EXIT_METADATA
    elif arm_id in CONDITIONAL_RUNNER_ARMS:
        metadata = _CONDITIONAL_RUNNER_METADATA
    if metadata is None:
        return revised

    source_revision = int(revised.get("strategy_revision") or 1)
    source = {
        "strategy_revision": source_revision,
        "arm_id": revised.get("arm_id"),
        "canonical_id": revised.get("canonical_id"),
        "stage": revised.get("stage"),
        "name": revised.get("name"),
        "behavior_contract_hash": revised.get("behavior_contract_hash"),
    }
    history = copy.deepcopy(revised.get("revision_history") or [])
    if not history:
        history.append(source)

    revised.update({
        "strategy_revision": 2,
        "revision_reason": metadata["reason"],
        "revision_changes": list(metadata["changes"]),
        "revision_basis": metadata["basis"],
        "revision_history": history,
    })
    if arm_id == INACTIVITY_ARM:
        revised["capital_exit_kind"] = "l0_loss_deterioration"
        revised["capital_exit_policy"] = copy.deepcopy(L0_LOSS_DETERIORATION_POLICY)
    elif arm_id == FLASH_ARM:
        entry_filter = copy.deepcopy(revised.get("entry_filter") or {})
        entry_filter.pop("max_m5_volume_usd_exclusive", None)
        entry_filter["min_m5_volume_usd"] = 200.0
        revised["entry_filter"] = entry_filter
    elif arm_id == MATURE_ARM:
        revised["entry_match_mode"] = "isolated_pattern_observer"
        revised["entry_revision_kind"] = "mature_confirmation"
    elif arm_id == "experiment_quiet_reawakening_candidate_v1":
        revised["entry_match_mode"] = "isolated_pattern_observer"
        revised["entry_revision_kind"] = "quiet_reawakening_confirmation"
        revised["entry_filter"] = {
            **copy.deepcopy(revised.get("entry_filter") or {}),
            "minimum_quiet_frames": 3,
            "minimum_quiet_span_seconds": 120.0,
            "maximum_quiet_lookback_seconds": 900.0,
            "quiet_max_trades": 2,
            "quiet_max_volume_usd": 200.0,
            "quiet_price_range_ratio": 1.10,
            "minimum_pool_age_seconds": 21_600.0,
            "trigger_min_trades": 10,
            "trigger_min_volume_usd": 1_000.0,
            "trigger_min_buy_ratio": 0.55,
            "trigger_price_reawakening_ratio": 1.12,
            "minimum_liquidity_retention": 0.80,
        }
    elif arm_id == "competing_risk_v1":
        revised["capital_revision_kind"] = "competing_risk_l0_confirmation"
        revised["source_period_seed_required"] = True
    elif arm_id == "duration_competing_risk_v1":
        revised["capital_revision_kind"] = "duration_risk_l0_confirmation"
        revised["source_period_seed_required"] = True
    elif arm_id in ACTIVITY_FLOOR_ARMS:
        entry_filter = copy.deepcopy(revised.get("entry_filter") or {})
        entry_filter["min_m5_trades"] = 3
        entry_filter["min_m5_volume_usd"] = 200.0
        revised["entry_filter"] = entry_filter
    elif arm_id in ADDITIVE_L0_LOSS_EXIT_ARMS:
        revised["revision_exit_kind"] = "l0_loss_deterioration"
        revised["revision_exit_policy"] = copy.deepcopy(
            L0_LOSS_DETERIORATION_POLICY
        )
    elif arm_id in CONDITIONAL_RUNNER_ARMS:
        revised["entry_match_mode"] = "isolated_pattern_observer"
        revised["entry_revision_kind"] = "conditional_runner_confirmation"
        revised["paired_entry_group"] = "conditional_runner_revision_v2"
    return revised


def evaluate_l0_loss_deterioration(
    position: Mapping[str, Any],
    frame: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
    *,
    now: Any,
    policy: Mapping[str, Any] = L0_LOSS_DETERIORATION_POLICY,
) -> ExitResult:
    """Arm a next-frame full exit after baseline plus two worsening L0 frames."""
    policy = _policy_snapshot(policy)
    new_state, evidence, error = _begin(
        "l0_loss_deterioration", policy, position, frame, state, now
    )
    if error:
        return _result(WAIT, error, new_state, evidence)
    if frame.get("original_pool") is not True:
        return _result(WAIT, "original_pool_identity_required", new_state, evidence)
    if new_state.get("status") == "EXIT_TRIGGERED":
        return _result(HOLD, "l0_loss_exit_already_triggered", new_state, evidence)
    if float(evidence["elapsed_seconds"]) < float(policy["minimum_hold_seconds"]):
        return _result(WAIT, "l0_loss_minimum_hold_not_reached", new_state, evidence)

    price = _number(frame.get("price_usd"))
    liquidity = _number(frame.get("liquidity_usd"))
    net_recovery = _number(frame.get("net_recovery_usd"))
    remaining_cost = _number(position.get("remaining_cost_usd"))
    evidence.update({
        "price_usd": price,
        "liquidity_usd": liquidity,
        "net_recovery_usd": net_recovery,
        "remaining_cost_usd": remaining_cost,
    })
    if (
        price is None or price <= 0.0 or liquidity is None or liquidity < 0.0
        or net_recovery is None or remaining_cost is None or remaining_cost < 0.0
    ):
        return _result(WAIT, "missing_l0_loss_evidence", new_state, evidence)

    prior = new_state.get("accepted_frame")
    if not isinstance(prior, Mapping):
        new_state["accepted_frame"] = _exit_frame(frame, price, liquidity)
        new_state["bad_streak"] = 0
        return _result(HOLD, "l0_loss_baseline_recorded", new_state, evidence)

    observed_at = _as_time(frame.get("observed_at"))
    prior_at = _as_time(prior.get("observed_at"))
    if observed_at is None or prior_at is None:
        return _result(WAIT, "missing_l0_loss_frame_span", new_state, evidence)
    span = (observed_at - prior_at).total_seconds()
    evidence["accepted_frame_span_seconds"] = span
    if span < float(policy["minimum_frame_span_seconds"]):
        return _result(WAIT, "l0_loss_frame_too_close", new_state, evidence)

    bad = bool(
        price < float(prior["price_usd"])
        and liquidity <= float(prior["liquidity_usd"])
    )
    streak = int(new_state.get("bad_streak") or 0) + 1 if bad else 0
    new_state["bad_streak"] = streak
    new_state["accepted_frame"] = _exit_frame(frame, price, liquidity)
    evidence.update({
        "l0_deterioration": bad,
        "deterioration_streak": streak,
        "below_remaining_cost": net_recovery < remaining_cost,
    })
    if streak >= int(policy["minimum_bad_frames"]) and net_recovery < remaining_cost:
        new_state["status"] = "EXIT_TRIGGERED"
        evidence.update(sell_fraction=1.0, required_fill="next_original_pool_frame")
        return _result(SELL, "l0_loss_deterioration_armed", new_state, evidence)
    return _result(HOLD, "l0_loss_deterioration_monitoring", new_state, evidence)


def _exit_frame(
    frame: Mapping[str, Any], price: float, liquidity: float
) -> dict[str, Any]:
    return {
        "frame_id": str(frame["frame_id"]),
        "observed_at": frame["observed_at"],
        "price_usd": price,
        "liquidity_usd": liquidity,
    }


def revision_entry_signal(
    history: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    decision_at: Any,
    activated_at: Any,
) -> tuple[bool, str]:
    """Confirm a revised entry using only recent identity-bound L0 frames."""
    kind = str(policy.get("entry_revision_kind") or "")
    needed = (
        2 if kind == "conditional_runner_confirmation"
        else 3 if kind == "mature_confirmation"
        else 4 if kind == "quiet_reawakening_confirmation"
        else 0
    )
    if needed == 0:
        return False, "unsupported_entry_revision"
    if len(history) < needed or len(history) > 80:
        return False, f"{kind}_awaiting_frames"
    frames = [dict(frame) for frame in history]
    error = _validate_entry_frames(frames, decision_at=decision_at, activated_at=activated_at)
    if error:
        return False, error
    if kind == "conditional_runner_confirmation":
        selected = _select_conditional_frames(frames)
        if selected is None:
            return False, "conditional_runner_confirmation_gap_not_met"
        return _conditional_runner_confirmation(selected)
    if kind == "quiet_reawakening_confirmation":
        return _quiet_reawakening_confirmation(frames, policy)
    selected = _select_mature_frames(frames)
    if selected is None:
        return False, "mature_confirmation_gap_not_met"
    return _mature_confirmation(selected, policy)


def revision_context_signal(
    history: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    decision_at: Any,
    activated_at: Any,
) -> tuple[bool, str]:
    """Revise zero-trade risk-model arms without discarding catastrophe risk."""
    kind = str(policy.get("capital_revision_kind") or "")
    if kind not in {"competing_risk_l0_confirmation", "duration_risk_l0_confirmation"}:
        return False, "unsupported_context_revision"
    if len(history) < 2 or len(history) > 80:
        return False, "risk_revision_awaiting_l0_frames"
    frames = [dict(frame) for frame in history]
    error = _validate_entry_frames(
        frames, decision_at=decision_at, activated_at=activated_at
    )
    if error:
        return False, error
    left, right = frames[-2:]
    gap = _frame_gap(left, right)
    left_market, right_market = _market_values(left), _market_values(right)
    assert left_market is not None and right_market is not None
    buys, sells = _integer(right.get("buys")), _integer(right.get("sells"))
    if (
        gap is None or not 0.0 < gap <= 30.0
        or right_market[0] < left_market[0]
        or right_market[1] < left_market[1]
        or buys is None or sells is None or buys + sells <= 0
    ):
        return False, "risk_revision_l0_confirmation_not_met"

    decision, activated = _time(decision_at), _time(activated_at)
    assert decision is not None and activated is not None
    if kind == "competing_risk_l0_confirmation":
        model = context.get("competing_risk")
        if not _risk_context_valid(model, decision, activated):
            return False, "wait_competing_risk_revision_model"
        assert isinstance(model, Mapping)
        profit = _number(model.get("p_profit"))
        death = _number(model.get("p_death"))
        if profit is None or death is None or profit <= death:
            return False, "competing_risk_catastrophe_not_dominated"
        return True, "competing_risk_l0_confirmation_ready"

    model = context.get("duration_risk")
    if not _risk_context_valid(model, decision, activated):
        return False, "wait_duration_risk_revision_model"
    assert isinstance(model, Mapping)
    horizon = str((policy.get("entry_filter") or {}).get("horizon_seconds", 300))
    probabilities = (model.get("gap_sensitivity") or {}).get(horizon)
    if not isinstance(probabilities, Mapping):
        return False, "wait_duration_risk_revision_probabilities"
    profit = _number(probabilities.get("profit_exit"))
    writeoff = _number(probabilities.get("writeoff_exit", 0.0))
    gap_risk = _number(probabilities.get("observation_gap", 0.0))
    if None in {profit, writeoff, gap_risk} or profit <= writeoff + gap_risk:
        return False, "duration_catastrophe_and_gap_not_dominated"
    return True, "duration_risk_l0_confirmation_ready"


def _risk_context_valid(
    value: Any, decision: datetime, activated: datetime
) -> bool:
    if not isinstance(value, Mapping) or value.get("sealed") is not True:
        return False
    observed = _time(value.get("observed_at"))
    recorded = _time(value.get("recorded_at"))
    cutoff = _time(value.get("cutoff_at"))
    trained = _time(value.get("trained_at"))
    return bool(
        observed and recorded and cutoff and trained
        and cutoff <= activated
        and cutoff <= trained <= decision
        and activated < observed <= recorded <= decision
        and (decision - observed).total_seconds() <= 30.0
        and value.get("sample_status") == "sufficient_sample"
    )


def _quiet_reawakening_confirmation(
    frames: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> tuple[bool, str]:
    cfg = policy.get("entry_filter") or {}
    latest = frames[-1]
    latest_at = _time(latest.get("observed_at"))
    assert latest_at is not None
    quiet = []
    for frame in frames[:-1]:
        observed = _time(frame.get("observed_at"))
        assert observed is not None
        age = (latest_at - observed).total_seconds()
        if 120.0 <= age <= float(cfg["maximum_quiet_lookback_seconds"]):
            if not quiet or (observed - _time(quiet[-1]["observed_at"])).total_seconds() >= 15.0:
                quiet.append(frame)
    minimum = int(cfg["minimum_quiet_frames"])
    if len(quiet) < minimum:
        return False, "quiet_revision_awaiting_baseline"
    quiet = quiet[-minimum:]
    span = (_time(quiet[-1]["observed_at"]) - _time(quiet[0]["observed_at"])).total_seconds()
    if span < float(cfg["minimum_quiet_span_seconds"]):
        return False, "quiet_revision_baseline_span_not_met"
    quiet_market = [_market_values(frame) for frame in quiet]
    assert all(value is not None for value in quiet_market)
    quiet_prices = [value[0] for value in quiet_market if value is not None]
    quiet_liquidity = [value[1] for value in quiet_market if value is not None]
    for frame in quiet:
        buys, sells = _integer(frame.get("buys")), _integer(frame.get("sells"))
        volume = _number(frame.get("volume"))
        if (
            buys is None or sells is None
            or buys + sells > int(cfg["quiet_max_trades"])
            or volume is None or volume > float(cfg["quiet_max_volume_usd"])
        ):
            return False, "quiet_revision_baseline_not_quiet"
    if max(quiet_prices) / min(quiet_prices) > float(cfg["quiet_price_range_ratio"]):
        return False, "quiet_revision_price_range_not_met"

    latest_market = _market_values(latest)
    assert latest_market is not None
    age = _number(latest.get("pool_age_seconds"))
    buys, sells = _integer(latest.get("buys")), _integer(latest.get("sells"))
    volume = _number(latest.get("volume"))
    if age is None or age < float(cfg["minimum_pool_age_seconds"]):
        return False, "quiet_revision_pool_not_mature"
    if buys is None or sells is None or buys + sells < int(cfg["trigger_min_trades"]):
        return False, "quiet_revision_trigger_activity_not_met"
    ratio = buys / (buys + sells)
    if (
        volume is None or volume < float(cfg["trigger_min_volume_usd"])
        or ratio < float(cfg["trigger_min_buy_ratio"])
        or latest_market[0] / quiet_prices[-1] < float(cfg["trigger_price_reawakening_ratio"])
        or latest_market[1] < quiet_liquidity[-1] * float(cfg["minimum_liquidity_retention"])
    ):
        return False, "quiet_revision_reawakening_not_met"
    return True, "quiet_reawakening_confirmation_ready"


def _select_mature_frames(
    frames: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]] | None:
    """Select two 15-90s confirmations while ignoring denser valid samples."""
    latest_index = len(frames) - 1
    first_index = _previous_frame_in_window(frames, latest_index, 15.0, 90.0)
    if first_index is None:
        return None
    baseline_index = _previous_frame_in_window(frames, first_index, 15.0, 90.0)
    if baseline_index is None:
        return None
    return frames[baseline_index], frames[first_index], frames[latest_index]


def _select_conditional_frames(
    frames: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    latest_index = len(frames) - 1
    first_index = _previous_frame_in_window(frames, latest_index, 15.0, 90.0)
    if first_index is None:
        return None
    return frames[first_index], frames[latest_index]


def _previous_frame_in_window(
    frames: Sequence[Mapping[str, Any]], right_index: int,
    minimum_seconds: float, maximum_seconds: float,
) -> int | None:
    right_at = _time(frames[right_index].get("observed_at"))
    if right_at is None:
        return None
    for index in range(right_index - 1, -1, -1):
        left_at = _time(frames[index].get("observed_at"))
        if left_at is None:
            continue
        gap = (right_at - left_at).total_seconds()
        if gap < minimum_seconds:
            continue
        if gap > maximum_seconds:
            break
        return index
    return None


def _validate_entry_frames(
    frames: Sequence[Mapping[str, Any]], *, decision_at: Any, activated_at: Any
) -> str | None:
    decision = _time(decision_at)
    activated = _time(activated_at)
    if decision is None or activated is None or decision < activated:
        return "invalid_entry_decision_time"
    identities = [_identity(frame) for frame in frames]
    if any(identity is None for identity in identities):
        return "missing_entry_identity"
    if len(set(identities)) != 1:
        return "mixed_entry_identity"

    prior_observed: datetime | None = None
    frame_ids: set[str] = set()
    for frame in frames:
        frame_id = str(frame.get("frame_id") or frame.get("id") or "").strip()
        observed = _time(frame.get("observed_at"))
        ingested = _time(frame.get("ingested_at"))
        recorded = _time(frame.get("recorded_at"))
        if not frame_id or frame_id in frame_ids:
            return "duplicate_or_missing_entry_frame"
        if None in {observed, ingested, recorded}:
            return "invalid_entry_frame_time"
        assert observed is not None and ingested is not None and recorded is not None
        if not (activated < observed <= ingested <= recorded <= decision):
            return "noncausal_or_future_entry_frame"
        if prior_observed is not None and observed <= prior_observed:
            return "duplicate_or_out_of_order_entry_frame"
        if _market_values(frame) is None:
            return "missing_entry_market_values"
        frame_ids.add(frame_id)
        prior_observed = observed
    assert prior_observed is not None
    if (decision - prior_observed).total_seconds() > 30.0:
        return "stale_entry_confirmation"
    return None


def _mature_confirmation(
    frames: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> tuple[bool, str]:
    baseline, first, second = frames
    entry_filter = policy.get("entry_filter") or {}
    age = _number(baseline.get("pool_age_seconds"))
    prior55 = _integer(baseline.get("prior55_trades"))
    if (
        age is None
        or age < float(entry_filter.get("min_age_seconds", 300.0))
        or age > float(entry_filter.get("max_age_seconds", 900.0))
        or prior55 is None
        or prior55 <= int(entry_filter.get("min_prior55_trades_exclusive", 2))
    ):
        return False, "mature_confirmation_baseline_not_met"
    for left, right in ((baseline, first), (first, second)):
        gap = _frame_gap(left, right)
        if gap is None or not 15.0 <= gap <= 90.0:
            return False, "mature_confirmation_gap_not_met"
    baseline_market = _market_values(baseline)
    assert baseline_market is not None
    for confirmation in (first, second):
        market = _market_values(confirmation)
        buys = _integer(confirmation.get("buys"))
        sells = _integer(confirmation.get("sells"))
        if buys is None or sells is None or buys + sells <= 0:
            return False, "mature_confirmation_activity_missing"
        assert market is not None
        if market[0] < baseline_market[0] or market[1] < baseline_market[1]:
            return False, "mature_confirmation_market_not_held"
    return True, "mature_confirmation_ready"


def _conditional_runner_confirmation(
    frames: tuple[Mapping[str, Any], Mapping[str, Any]],
) -> tuple[bool, str]:
    first, second = frames
    for frame in frames:
        age = _number(frame.get("pool_age_seconds"))
        buys = _integer(frame.get("buys"))
        sells = _integer(frame.get("sells"))
        if (
            age is None or age > 900.0 or buys is None or sells is None
            or buys + sells < 3
        ):
            return False, "conditional_runner_filter_not_met"
    first_market = _market_values(first)
    second_market = _market_values(second)
    assert first_market is not None and second_market is not None
    if second_market[0] < first_market[0] or second_market[1] < first_market[1]:
        return False, "conditional_runner_market_reversed"
    return True, "conditional_runner_confirmation_ready"


def _identity(frame: Mapping[str, Any]) -> tuple[str, str, str] | None:
    identity = frame.get("identity")
    source = identity if isinstance(identity, Mapping) else frame
    token_id = str(source.get("token_id") or "").strip()
    pair_address = str(source.get("pair_address") or "").strip()
    chain = str(source.get("chain") or token_id.partition(":")[0]).strip().lower()
    if not chain or not token_id or not pair_address:
        return None
    return chain, token_id, pair_address


def _market_values(frame: Mapping[str, Any]) -> tuple[float, float] | None:
    price = _number(frame.get("price"))
    liquidity = _number(frame.get("liquidity"))
    if price is None or price <= 0.0 or liquidity is None or liquidity < 0.0:
        return None
    return price, liquidity


def _frame_gap(left: Mapping[str, Any], right: Mapping[str, Any]) -> float | None:
    left_at = _time(left.get("observed_at"))
    right_at = _time(right.get("observed_at"))
    if left_at is None or right_at is None:
        return None
    return (right_at - left_at).total_seconds()


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "INACTIVITY_ARM",
    "FLASH_ARM",
    "MATURE_ARM",
    "ACTIVITY_FLOOR_ARMS",
    "ADDITIVE_L0_LOSS_EXIT_ARMS",
    "CONDITIONAL_RUNNER_ARMS",
    "L0_LOSS_DETERIORATION_POLICY",
    "revision_spec",
    "revision_entry_signal",
    "revision_context_signal",
    "evaluate_l0_loss_deterioration",
]
