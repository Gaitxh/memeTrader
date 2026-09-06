"""Forward replacements for evidence-starved entry policies.

The replacements use only the same-pool L0 frames already supplied to the
pattern dispatcher.  Aggregate trades and volume are market-activity proxies;
they are never relabelled as wallets, creator facts, event facts, or decoded
money flow.  Persistence and next-frame execution remain Store concerns.
"""
from __future__ import annotations

import copy
import math
from statistics import median
from typing import Any, Mapping, Sequence

from .models import CHAIN_MEME_MIN_POOL_LIQUIDITY_USD, parse_time


ENTRY_REVISION_KIND = "evidence_extension_l0"


def _spec(kind: str, name: str, hypothesis: str, **thresholds: Any) -> dict[str, Any]:
    return {"kind": kind, "name": name, "hypothesis": hypothesis, **thresholds}


SPECS: dict[str, dict[str, Any]] = {
    "experiment_narrative_candidate_v1": _spec(
        "early_quality", "早期平均成交质量", "小额噪声较少的早期活跃是否优于不可用叙事门",
        max_age=900, min_trades=5, min_volume=500, min_average_trade=50, min_buy_ratio=.55),
    "experiment_narrative_control_v1": _spec(
        "continuation", "早期价格流动性连续", "两个独立L0帧的不退连续性是否优于不可用叙事门",
        max_age=900, min_frames=2, min_span=10, min_trades=4, min_volume=300,
        min_buy_ratio=.5, min_price_ratio=1.0, max_price_ratio=1.18,
        min_liquidity_retention=.9, min_volume_acceleration=.8),
    "finite_capital_ranker_v1": _spec(
        "quality_gate", "单币可执行质量门", "不用缺失横截面排名，检验单币流动性与活动质量门",
        max_age=21600, min_trades=8, min_volume=1200, min_average_trade=75,
        min_buy_ratio=.55, min_liquidity=5000),
    "market_regime_throttle_v1": _spec(
        "reawakening", "单币静默后恢复", "不用缺失全市场regime，以同池静默到恢复检验局部状态切换",
        min_age=1800, min_frames=4, min_span=30, quiet_max_trades=3,
        quiet_max_volume=300, min_trades=10, min_volume=1200,
        min_buy_ratio=.55, min_price_ratio=1.08, min_liquidity_retention=.85),
    "direct_lp_float_constrained_v1": _spec(
        "liquidity_lead", "流动性先行小额试验", "不推断LP控制，检验可见流动性扩张先于价格",
        max_age=3600, min_frames=3, min_span=20, min_liquidity_growth=1.20,
        min_price_ratio=.98, max_price_ratio=1.12, min_trades=5,
        min_volume=400, min_buy_ratio=.5),
    "authoritative_event_shock_v1": _spec(
        "young_absorption", "年轻池承接确认", "没有官方事件时，独立检验年轻池价格与流动性共同承接",
        max_age=1800, min_frames=3, min_span=20, min_trades=8,
        min_volume=800, min_buy_ratio=.55, min_price_ratio=1.03,
        max_price_ratio=1.25, min_liquidity_retention=.95),
    "event_reawakening_v1": _spec(
        "reawakening", "成熟池静默复苏", "不声称事件，检验成熟同池静默后活动与价格复苏",
        min_age=3600, min_frames=4, min_span=30, quiet_max_trades=2,
        quiet_max_volume=200, min_trades=10, min_volume=1000,
        min_buy_ratio=.6, min_price_ratio=1.10, min_liquidity_retention=.8),
    "surface_lifecycle_pipeline_v1": _spec(
        "liquidity_lead", "成熟池深度延续", "不声称surface分类，检验成熟池流动性增长且价格未过热",
        min_age=3600, min_frames=3, min_span=20, min_liquidity_growth=1.15,
        min_price_ratio=1.0, max_price_ratio=1.15, min_trades=8,
        min_volume=1000, min_buy_ratio=.55),
    "no_ca_event_flow_leader_v1": _spec(
        "compression_breakout", "压缩后活动突破", "不用CA事件或资金leader，检验同池压缩后的公开活动突破",
        max_age=21600, min_frames=4, min_span=30, max_baseline_range=1.05,
        min_breakout=1.06, max_breakout=1.20, min_volume_acceleration=1.5,
        min_liquidity_retention=.9, min_trades=8, min_buy_ratio=.55),
    "direct_lp_amount_specific_confirmed_v1": _spec(
        "early_quality", "年轻池大单均值代理", "取消未覆盖的特殊预检入场，检验早期公开成交均值质量",
        max_age=1800, min_trades=6, min_volume=900, min_average_trade=100,
        min_buy_ratio=.55),
    "official_event_actual_flow_v1": _spec(
        "continuation", "多帧买方活动延续", "不声称官方事件或真实金额流，检验公开活动的多帧延续",
        max_age=3600, min_frames=3, min_span=20, min_trades=8,
        min_volume=800, min_buy_ratio=.6, min_price_ratio=1.02,
        max_price_ratio=1.20, min_liquidity_retention=.9,
        min_volume_acceleration=1.0),
    "migration_amount_rate_absorption_v1": _spec(
        "young_absorption", "年轻池三帧吸收", "不冒充迁移receipt或金额窗，检验年轻池三帧承接",
        max_age=2400, min_frames=3, min_span=20, min_trades=10,
        min_volume=1200, min_buy_ratio=.6, min_price_ratio=1.04,
        max_price_ratio=1.22, min_liquidity_retention=1.0),
    "experiment_participation_candidate_v1": _spec(
        "early_quality", "早期参与强度代理", "不把交易数冒充独立钱包，检验公开交易强度与买方倾斜",
        max_age=900, min_trades=12, min_volume=1000, min_average_trade=40,
        min_buy_ratio=.6),
    "capital_velocity_v1": _spec(
        "continuation", "公开成交额加速", "真实金额流稀疏时，独立检验两帧公开成交额加速",
        max_age=3600, min_frames=2, min_span=10, min_trades=8,
        min_volume=1000, min_buy_ratio=.55, min_price_ratio=1.0,
        max_price_ratio=1.18, min_liquidity_retention=.9,
        min_volume_acceleration=1.5),
    "prebreakout_net_accumulation_v1": _spec(
        "compression_breakout", "窄幅蓄势后二次确认", "以严格压缩和活动加速替代不可稳定取得的净资金积累",
        max_age=21600, min_frames=5, min_span=40, max_baseline_range=1.04,
        min_breakout=1.05, max_breakout=1.15, min_volume_acceleration=1.5,
        min_liquidity_retention=.95, min_trades=8, min_buy_ratio=.58),
    "liquidity_leads_price_v1": _spec(
        "liquidity_lead", "连续流动性领先", "原低频结果偏弱，改为三帧深度增长且价格仍受控",
        max_age=21600, min_frames=3, min_span=20, min_liquidity_growth=1.30,
        min_price_ratio=1.0, max_price_ratio=1.08, min_trades=8,
        min_volume=800, min_buy_ratio=.58),
    "common_funding_adjusted_breadth_5u_v1": _spec(
        "continuation", "公开活动持续性5U", "不以稀疏资金关系推断控制者，改测三帧公开活动持续性",
        max_age=3600, min_frames=3, min_span=20, min_trades=6,
        min_volume=600, min_buy_ratio=.55, min_price_ratio=1.0,
        max_price_ratio=1.15, min_liquidity_retention=.95,
        min_volume_acceleration=.9),
}


def revise_evidence_extension(policy: Mapping[str, Any]) -> dict[str, Any]:
    """Return an explicit forward replacement for one of the 17 owned arms."""
    revised = copy.deepcopy(dict(policy))
    arm_id = str(revised.get("arm_id") or "")
    spec = SPECS.get(arm_id)
    if spec is None:
        return revised
    prior_family = str(revised.get("entry_family") or "unknown")
    source_revision = int(revised.get("strategy_revision") or 1)
    thresholds = {k: copy.deepcopy(v) for k, v in spec.items()
                  if k not in {"kind", "name", "hypothesis"}}
    revised.update({
        "strategy_revision": source_revision + 1,
        "name": spec["name"],
        "description": (
            f"替换旧{prior_family}入场；只使用部署后同池L0价格、流动性、"
            "成交额与聚合交易数，尚未证明盈利。"
        ),
        "entry_family": "evidence_extension_l0",
        "source_entry_family": prior_family,
        "entry_revision_kind": ENTRY_REVISION_KIND,
        "entry_filter": {"direction": spec["kind"], **thresholds},
        "required_inputs": [
            "post_deployment_same_pool_l0_history",
            "price_liquidity_volume_aggregate_transactions",
        ],
        "replacement_of_entry_family": prior_family,
        "replacement_hypothesis": spec["hypothesis"],
        "replacement_input_contract": "existing_same_pool_l0_no_new_api/v1",
        "revision_reason": (
            f"旧{prior_family}方向因必要证据缺失或自然机会过少，不能形成可学习的前向样本"
        ),
        "revision_changes": [
            f"以{spec['name']}替换旧入场，不伪造事件、钱包、路由或真实金额流",
            "保留原策略ID、名义金额、独立账户、退出和下一独立帧成交合同",
        ],
        "revision_basis": (
            "候选矩阵将该臂列为零证据或超过10小时仅1至2次BUY；"
            "替代输入已存在于同池L0观察，不增加API或扫描预算"
        ),
        "fidelity_status": "REPLACED_FORWARD",
        "no_historical_backfill": True,
    })
    # Former candidate/control labels no longer imply a shared entry mechanism.
    revised.pop("paired_entry_group", None)
    revised.pop("paired_opportunity_group", None)
    return revised


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _frames(history: Sequence[Mapping[str, Any]], *, decision_at: Any,
            activated_at: Any) -> tuple[list[dict[str, Any]], str | None]:
    if not history:
        return [], "awaiting_l0_observation"
    decision, activated = parse_time(decision_at), parse_time(activated_at)
    if decision < activated:
        return [], "noncausal_revision_time"
    latest = history[-1]
    token, pair = str(latest.get("token_id") or ""), str(latest.get("pair_address") or "")
    if not token or not pair:
        return [], "same_pool_identity_required"
    selected: list[dict[str, Any]] = []
    for raw in history[-8:]:
        if str(raw.get("token_id") or "") != token or str(raw.get("pair_address") or "") != pair:
            continue
        try:
            observed = parse_time(raw.get("observed_at"))
            ingested = parse_time(raw.get("ingested_at"))
            recorded = parse_time(raw.get("recorded_at"))
        except (TypeError, ValueError):
            continue
        if not activated <= observed <= ingested <= recorded <= decision:
            continue
        price, liquidity, volume = (_number(raw.get(k)) for k in ("price", "liquidity", "volume"))
        buys, sells, age = (_number(raw.get(k)) for k in ("buys", "sells", "pool_age_seconds"))
        if (price is None or price <= 0 or liquidity is None or liquidity < 0
                or volume is None or volume < 0 or buys is None or buys < 0
                or sells is None or sells < 0 or age is None or age < 0):
            continue
        selected.append({**dict(raw), "observed_dt": observed, "price": price,
                         "liquidity": liquidity, "volume": volume,
                         "buys": buys, "sells": sells, "pool_age_seconds": age})
    if not selected or selected[-1].get("observed_at") != latest.get("observed_at"):
        return [], "latest_l0_frame_noncausal_or_invalid"
    if not 0 <= (decision - selected[-1]["observed_dt"]).total_seconds() <= 30:
        return [], "latest_l0_frame_stale"
    selected = [frame for i, frame in enumerate(selected)
                if i == 0 or frame["observed_dt"] > selected[i - 1]["observed_dt"]]
    return selected, None


def _ratio(frame: Mapping[str, Any]) -> float:
    total = float(frame["buys"]) + float(frame["sells"])
    return float(frame["buys"]) / total if total > 0 else 0.0


def evaluate_evidence_extension_entry(
    history: Sequence[Mapping[str, Any]], policy: Mapping[str, Any], *,
    decision_at: Any, activated_at: Any,
) -> tuple[bool, str]:
    """Evaluate one replacement signal; execution still requires a later frame."""
    if policy.get("entry_revision_kind") != ENTRY_REVISION_KIND:
        return False, "unsupported_evidence_extension"
    frames, error = _frames(history, decision_at=decision_at, activated_at=activated_at)
    if error:
        return False, error
    cfg = policy.get("entry_filter") or {}
    kind = str(cfg.get("direction") or "")
    last = frames[-1]
    floor = float((policy.get("_execution") or {}).get(
        "min_pool_liquidity_usd", CHAIN_MEME_MIN_POOL_LIQUIDITY_USD))
    if last["liquidity"] < max(floor, float(cfg.get("min_liquidity", 0.0))):
        return False, "replacement_pool_liquidity_below_floor"
    if not float(cfg.get("min_age", 0.0)) <= last["pool_age_seconds"] <= float(cfg.get("max_age", math.inf)):
        return False, "replacement_pool_age_not_met"
    minimum = int(cfg.get("min_frames", 1))
    if len(frames) < minimum:
        return False, "awaiting_replacement_l0_sequence"
    window = frames[-minimum:]
    if minimum > 1:
        span = (window[-1]["observed_dt"] - window[0]["observed_dt"]).total_seconds()
        if span < float(cfg.get("min_span", 0.0)):
            return False, "replacement_l0_span_not_met"
        if any((right["observed_dt"] - left["observed_dt"]).total_seconds() > 90
               for left, right in zip(window, window[1:])):
            return False, "replacement_l0_gap_too_large"
    trades = last["buys"] + last["sells"]
    if trades < float(cfg.get("min_trades", 0)) or last["volume"] < float(cfg.get("min_volume", 0)):
        return False, "replacement_activity_not_met"
    if _ratio(last) < float(cfg.get("min_buy_ratio", 0.0)):
        return False, "replacement_buy_ratio_not_met"

    passed = False
    if kind in {"early_quality", "quality_gate"}:
        passed = trades > 0 and last["volume"] / trades >= float(cfg.get("min_average_trade", 0.0))
    elif kind == "continuation":
        first = window[0]
        passed = (
            float(cfg["min_price_ratio"]) <= last["price"] / first["price"] <= float(cfg["max_price_ratio"])
            and last["liquidity"] >= first["liquidity"] * float(cfg["min_liquidity_retention"])
            and last["volume"] >= first["volume"] * float(cfg["min_volume_acceleration"])
            and all(_ratio(frame) >= float(cfg["min_buy_ratio"]) for frame in window[-2:])
        )
    elif kind == "liquidity_lead":
        first = window[0]
        passed = (
            last["liquidity"] >= first["liquidity"] * float(cfg["min_liquidity_growth"])
            and float(cfg["min_price_ratio"]) <= last["price"] / first["price"] <= float(cfg["max_price_ratio"])
        )
    elif kind == "compression_breakout":
        baseline = window[:-1]
        base_price = median(frame["price"] for frame in baseline)
        base_volume = median(frame["volume"] for frame in baseline)
        passed = (
            max(frame["price"] for frame in baseline) / min(frame["price"] for frame in baseline)
            <= float(cfg["max_baseline_range"])
            and float(cfg["min_breakout"]) <= last["price"] / base_price <= float(cfg["max_breakout"])
            and base_volume > 0
            and last["volume"] >= base_volume * float(cfg["min_volume_acceleration"])
            and last["liquidity"] >= median(frame["liquidity"] for frame in baseline)
            * float(cfg["min_liquidity_retention"])
        )
    elif kind == "reawakening":
        quiet = window[:-1]
        passed = bool(quiet) and (
            max(frame["buys"] + frame["sells"] for frame in quiet) <= float(cfg["quiet_max_trades"])
            and max(frame["volume"] for frame in quiet) <= float(cfg["quiet_max_volume"])
            and last["price"] >= median(frame["price"] for frame in quiet) * float(cfg["min_price_ratio"])
            and last["liquidity"] >= median(frame["liquidity"] for frame in quiet)
            * float(cfg["min_liquidity_retention"])
        )
    elif kind == "young_absorption":
        first = window[0]
        passed = (
            float(cfg["min_price_ratio"]) <= last["price"] / first["price"] <= float(cfg["max_price_ratio"])
            and min(frame["liquidity"] for frame in window)
            >= first["liquidity"] * float(cfg["min_liquidity_retention"])
            and all(_ratio(frame) >= .5 for frame in window[-2:])
        )
    else:
        return False, "unsupported_evidence_extension_direction"
    return bool(passed), (
        f"replacement_{kind}_confirmed" if passed else f"replacement_{kind}_conditions_not_met"
    )


__all__ = [
    "ENTRY_REVISION_KIND", "SPECS", "revise_evidence_extension",
    "evaluate_evidence_extension_entry",
]
