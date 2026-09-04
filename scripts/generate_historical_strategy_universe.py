from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


EXPECTED_VERSION_COUNT = 13
EXPECTED_POLICIES_PER_VERSION = 12
EXPECTED_INSTANCE_COUNT = 156

PAPER_CANDIDATE = "PAPER_CANDIDATE"
SHADOW_CANDIDATE = "SHADOW_CANDIDATE"
RETIRED_ECONOMIC_FAILURE = "RETIRED_ECONOMIC_FAILURE"
RETIRED_ENGINEERING_FAILURE = "RETIRED_ENGINEERING_FAILURE"
SUPERSEDED_REUSABLE = "SUPERSEDED_REUSABLE"
INVALID_OR_UNCOMPARABLE = "INVALID_OR_UNCOMPARABLE"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()[:16]


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def _trimmed_mean(values: list[float], fraction: float = 0.10) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    trim = int(len(ordered) * fraction)
    kept = ordered[trim : len(ordered) - trim] if trim and len(ordered) > 2 * trim else ordered
    return sum(kept) / len(kept)


def _version_number(version: str) -> int:
    try:
        return int(version.split("/v", 1)[1].split("-", 1)[0])
    except (IndexError, ValueError):
        return 0


def _rows(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql).fetchall()]


def _group(rows: Iterable[dict[str, Any]], *keys: str) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(key) for key in keys)].append(row)
    return grouped


def _clean_policy(policy: dict[str, Any]) -> dict[str, Any]:
    ignored = {"arm_id", "name", "description", "stage", "behavior_equivalence_expected"}
    return {key: policy[key] for key in sorted(policy) if key not in ignored}


def _display_name(arm_id: str, fallback: Any) -> str:
    fixed = {
        "fixed_15m": "固定 15 分钟",
        "fixed_60m": "固定 60 分钟",
        "fixed_240m": "固定 240 分钟",
        "hard_stop_35": "硬止损 35%",
        "take_profit_80": "止盈 80%",
        "stop35_tp80": "止损 35% + 止盈 80%",
        "trailing_60_28": "60% 启动 / 28% 回撤移动止盈",
        "liquidity_3000": "流动性 3000U 紧急退出",
        "inactivity_5m": "5 分钟无活动退出",
        "flow_fade_45": "买盘衰减退出",
        "winner_runner": "赢家延长持有",
        "composite_dynamic": "组合动态退出",
        "stage_01_shadow_v1": "链上 Shadow v1",
        "stage_02_jupiter_v1": "双向路线 v1",
        "stage_03_fixed_paper_v1": "固定周期 Paper v1",
        "stage_04_dynamic_v1": "动态退出 Challenger v1",
        "stage_05_fair_start_v2": "Fair-start v2",
        "stage_06_economic_v3": "Economic-execution v3",
        "stage_07_cost_v4": "公平成本 v4",
        "stage_08_rug_safety": "买前 Rug Safety",
        "stage_09_executable_equity": "可执行权益监控",
        "stage_10_dead_route_backoff": "死亡路线退避",
        "stage_11_exact_rug_terminal": "精确账户监听与 Rug 终态",
        "stage_12_solana_focus": "Solana Focus Epoch",
    }
    if arm_id in fixed:
        return fixed[arm_id]
    if "__" in arm_id:
        entry, exit_family = arm_id.split("__", 1)
        entries = {"broad_launch": "宽口径新发", "flow_burst": "流量突发", "reawakening": "沉寂复苏"}
        exits = {"fast_escape": "快速逃生", "balanced_harvest": "均衡收获", "peak_guard": "峰值保护", "postbuy_research": "买后研究"}
        return f"{entries.get(entry, entry)} × {exits.get(exit_family, exit_family)}"
    text = str(fallback or arm_id)
    return arm_id if "�" in text else text


def _contract(definition: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    # Include every frozen global trading/execution field except the epoch label
    # and the list of sibling policies.  This intentionally keeps capital,
    # quote/fill, valuation, no-route and terminal semantics in the fingerprint.
    global_contract = {
        key: definition[key]
        for key in sorted(definition)
        if key not in {"version", "policies"}
    }
    return {"global": global_contract, "policy": _clean_policy(policy)}


def _failure_profile(version: str, stop_reason: str | None) -> tuple[str, str, str]:
    reason = (stop_reason or "").lower()
    if "negative_cash" in reason:
        return (
            "ENGINEERING_ACCOUNTING",
            "负现金 epoch 破坏账户与收益真值，不能形成经济结论",
            "保留入场/退出规则；禁止复用该 epoch 的现金与 PNL",
        )
    if "scheduler_interference" in reason:
        return (
            "ENGINEERING_SCHEDULER",
            "执行调度相互干扰，样本暴露与成交机会不再可比",
            "保留策略参数；禁止把受干扰交易作为策略优劣证据",
        )
    if "invalid_direct_curve" in reason:
        return (
            "INVALID_TERMINAL_SEMANTICS",
            "本池容量被错误提升为聚合市场终态，核销语义无效",
            "保留本池观察特征；禁止把 local no-capacity 当全市场不可卖",
        )
    if "invalid_no_route_only_writeoff" in reason:
        return (
            "INVALID_NO_ROUTE_SEMANTICS",
            "单一 no-route 被错误当作全损，污染终局结果",
            "保留路线观察；禁止用单一 provider no-route 直接核销",
        )
    if "weakest_arm_cash_veto" in reason:
        return (
            "ENGINEERING_CAPITAL_VETO",
            "最弱账户现金状态阻塞同族其他账户，参与样本被系统性压低",
            "保留独立策略逻辑；禁止共享最弱现金 veto",
        )
    if "continuous_jupiter_valuation" in reason:
        return (
            "SUPERSEDED_VALUATION_CONTRACT",
            "持续 Jupiter 估值被轻量市场标记合同替代",
            "保留 amount-specific 执行研究；禁止恢复高频受限报价",
        )
    if "jupiter_buy_dependency" in reason:
        return (
            "SUPERSEDED_ENTRY_EXECUTION",
            "Jupiter BUY 依赖限制采样，被下一报价 DEX mark Paper 合同替代",
            "保留动态退出与成本模型；禁止将报价缺失当市场无机会",
        )
    if stop_reason:
        return (
            "SUPERSEDED_CONTRACT",
            stop_reason,
            "保留未被新合同否定的组件；禁止跨合同直接合并 PNL",
        )
    if _version_number(version) < 13:
        return (
            "IMPLICIT_SUPERSESSION",
            "数据库无显式 stop row，但后续版本已注册；仅按旧合同基线保留",
            "保留定义与历史证据；禁止把旧 epoch 当当前运行策略",
        )
    return ("ACTIVE_FORWARD", "当前 v13 前向运行", "继续收集严格前向证据")


def _classification(
    *, version: str, stop_reason: str | None, terminal_pnls: list[float],
    positive_block_ratio: float | None, concentration: float | None,
) -> tuple[str, str, str]:
    failure_type, root_cause, reusable = _failure_profile(version, stop_reason)
    count = len(terminal_pnls)
    total = sum(terminal_pnls)
    median = statistics.median(terminal_pnls) if terminal_pnls else None
    trimmed = _trimmed_mean(terminal_pnls)
    if failure_type.startswith("INVALID"):
        return INVALID_OR_UNCOMPARABLE, root_cause, reusable
    if failure_type.startswith("ENGINEERING"):
        return RETIRED_ENGINEERING_FAILURE, root_cause, reusable
    sufficient = count >= 30 and positive_block_ratio is not None
    robust_positive = (
        sufficient and total > 0 and (median or 0) > 0 and (trimmed or 0) > 0
        and positive_block_ratio >= 0.50
        and (concentration is None or concentration <= 0.75)
    )
    robust_negative = sufficient and total <= 0 and (median or 0) <= 0 and (trimmed or 0) <= 0
    if robust_positive:
        return PAPER_CANDIDATE, "多指标、跨时间块的扣摩擦终局证据为正", reusable
    if robust_negative:
        return RETIRED_ECONOMIC_FAILURE, "成熟终局样本的总计、中位数与截尾均值均不为正", reusable
    if failure_type.startswith("SUPERSEDED") or failure_type == "IMPLICIT_SUPERSESSION":
        if count > 0 and total > 0 and (trimmed or 0) > 0:
            return SHADOW_CANDIDATE, "旧合同存在正向信号，但样本/稳定性不足以进入 Paper", reusable
        return SUPERSEDED_REUSABLE, root_cause, reusable
    return SHADOW_CANDIDATE, "当前合同仍在学习，证据尚不足以晋级 Paper", reusable


def build_report(database: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        registrations = _rows(
            connection,
            "SELECT definition_version,registered_at,activation_exploration_buy_trade_id,"
            "definition_json FROM chain_meme_trader_registrations ORDER BY registered_at",
        )
        activations = {
            row["definition_version"]: row for row in _rows(
                connection, "SELECT * FROM chain_meme_trader_v6_activations"
            )
        }
        stops = {
            row["definition_version"]: row for row in _rows(
                connection, "SELECT * FROM chain_meme_trader_primary_stops"
            )
        }
        decisions = _group(_rows(connection, "SELECT * FROM chain_meme_trader_entry_decisions"), "definition_version", "arm_id")
        positions = _group(_rows(connection, "SELECT * FROM chain_meme_trader_positions"), "definition_version", "arm_id")
        trades = _group(_rows(connection, "SELECT * FROM chain_meme_trader_trades"), "definition_version", "arm_id")
        participants = _group(_rows(connection, "SELECT * FROM chain_meme_trader_entry_participant_outcomes"), "definition_version", "arm_id")
        latest_accounts = {
            (row["definition_version"], row["arm_id"]): row
            for row in _rows(
                connection,
                "SELECT s.* FROM chain_meme_trader_account_snapshots s JOIN ("
                "SELECT definition_version,arm_id,MAX(id) AS id "
                "FROM chain_meme_trader_account_snapshots GROUP BY definition_version,arm_id"
                ") x ON x.id=s.id",
            )
        }
        quote_stats = {
            row["definition_version"]: row for row in _rows(
                connection,
                "SELECT definition_version,COUNT(*) AS quote_count,"
                "SUM(quote_terminal_status='quoted' AND validity_status='valid') AS valid_quoted,"
                "SUM(quote_terminal_status='no_route') AS no_route,"
                "SUM(quote_terminal_status='error') AS errors "
                "FROM chain_meme_trader_quote_results GROUP BY definition_version",
            )
        }
    finally:
        connection.close()

    definitions = {
        row["definition_version"]: json.loads(row["definition_json"])
        for row in registrations
    }
    policy_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    entry_siblings: dict[tuple[str, str], list[str]] = defaultdict(list)
    for version, definition in definitions.items():
        for policy in definition.get("policies", []):
            arm_id = str(policy["arm_id"])
            policy_lookup[(version, arm_id)] = policy
            entry = str(policy.get("entry_family") or policy.get("entry_gate") or policy.get("family") or "unknown")
            entry_siblings[(version, entry)].append(arm_id)

    position_cohorts = {
        key: {int(row["shadow_cohort_id"]) for row in rows}
        for key, rows in positions.items()
    }
    terminal_cohorts = {
        key: {
            int(row["shadow_cohort_id"]) for row in rows
            if row["status"] in {"closed", "written_off"}
        }
        for key, rows in positions.items()
    }

    instances: list[dict[str, Any]] = []
    for registration in registrations:
        version = str(registration["definition_version"])
        definition = definitions[version]
        activation = activations.get(version, {})
        stop = stops.get(version, {})
        for policy in definition.get("policies", []):
            arm_id = str(policy["arm_id"])
            key = (version, arm_id)
            decision_rows = decisions.get(key, [])
            position_rows = positions.get(key, [])
            trade_rows = trades.get(key, [])
            participant_rows = participants.get(key, [])
            terminal_rows = [row for row in position_rows if row["status"] in {"closed", "written_off"}]
            terminal_values = [float(row.get("realized_pnl_usd") or 0.0) for row in terminal_rows]
            daily: dict[str, float] = defaultdict(float)
            daily_counts: dict[str, int] = defaultdict(int)
            daily_wins: dict[str, int] = defaultdict(int)
            for row in terminal_rows:
                day = str(row.get("closed_at") or "UNKNOWN")[:10]
                value = float(row.get("realized_pnl_usd") or 0.0)
                daily[day] += value
                daily_counts[day] += 1
                daily_wins[day] += int(value > 0.0)
            blocks = [value for day, value in daily.items() if day != "UNKNOWN"]
            positive_total = sum(value for value in terminal_values if value > 0)
            concentration = max(terminal_values) / positive_total if terminal_values and positive_total > 0 else None
            positive_block_ratio = sum(value > 0 for value in blocks) / len(blocks) if blocks else None
            entry_family = str(policy.get("entry_family") or policy.get("entry_gate") or policy.get("family") or "unknown")
            sibling_arms = entry_siblings[(version, entry_family)]
            sibling_intersections = []
            terminal_intersections = []
            own = position_cohorts.get(key, set())
            own_terminal = terminal_cohorts.get(key, set())
            for sibling in sibling_arms:
                if sibling == arm_id:
                    continue
                sibling_intersections.append(len(own & position_cohorts.get((version, sibling), set())))
                terminal_intersections.append(len(own_terminal & terminal_cohorts.get((version, sibling), set())))
            classification, classification_reason, reusable = _classification(
                version=version,
                stop_reason=stop.get("reason"),
                terminal_pnls=terminal_values,
                positive_block_ratio=positive_block_ratio,
                concentration=concentration,
            )
            invalid = classification in {RETIRED_ENGINEERING_FAILURE, INVALID_OR_UNCOMPARABLE}
            terminal_count = len(terminal_values)
            evidence_grade = (
                "INVALID" if invalid else
                "A" if classification == PAPER_CANDIDATE else
                "B" if terminal_count >= 30 and len(blocks) >= 2 else
                "C" if terminal_count > 0 else "INSUFFICIENT"
            )
            contract = _contract(definition, policy)
            account = latest_accounts.get(key, {})
            qstats = quote_stats.get(version, {})
            instance = {
                "strategy_key": f"{version}::{arm_id}",
                "version": version,
                "version_number": _version_number(version),
                "registered_at": registration.get("registered_at"),
                "activation_frontier": {
                    "exploration_buy_trade_id": registration.get("activation_exploration_buy_trade_id"),
                    "snapshot_id": activation.get("activation_snapshot_id"),
                    "source_frontier": activation.get("v5_source_frontier"),
                    "activated_at": activation.get("activated_at"),
                },
                "stopped_at": stop.get("stopped_at"),
                "stop_reason": stop.get("reason") or (
                    "active_v13" if _version_number(version) == 13 else "implicit_superseded_no_stop_row"
                ),
                "arm_id": arm_id,
                "stage": policy.get("stage"),
                "name": _display_name(arm_id, policy.get("name")),
                "entry_family": entry_family,
                "exit_family": str(policy.get("exit_family") or policy.get("exit_mode") or policy.get("family") or "unknown"),
                "frozen_policy": _clean_policy(policy),
                "execution_contract": {
                    "source": definition.get("source"),
                    "execution": definition.get("execution"),
                    "execution_profile": definition.get("execution_profile") or policy.get("execution_profile"),
                    "buy_execution": definition.get("buy_execution"),
                    "sell_execution": definition.get("sell_execution"),
                    "valuation": definition.get("valuation"),
                    "capital_eligibility": definition.get("capital_eligibility") or definition.get("entry_cash_reservation"),
                    "notional_usd": definition.get("policy_notional_usd"),
                    "slippage_bps": definition.get("slippage_bps"),
                    "additional_fee_usd_each_fill": definition.get("additional_fee_usd_each_fill"),
                    "no_route_semantics": definition.get("single_no_route_without_exact_pool_evidence"),
                    "terminal_semantics": definition.get("confirmed_pool_removed_and_no_route") or definition.get("pool_missing_terminal"),
                    "live_execution": bool(definition.get("live_execution", False)),
                },
                "behavior_contract_hash": _hash(contract),
                "behavior_contract": contract,
                "samples": {
                    "decisions": len(decision_rows),
                    "admitted_decisions": sum(row["status"] == "admitted" for row in decision_rows),
                    "rejected_decisions": sum(row["status"] == "rejected" for row in decision_rows),
                    "decision_cohorts": len({int(row["shadow_cohort_id"]) for row in decision_rows}),
                    "participated_cohorts": len(position_cohorts.get(key, set())),
                    "terminal_cohorts": len(terminal_cohorts.get(key, set())),
                    "projected_participations": sum(row.get("outcome") == "projected" for row in participant_rows),
                    "skipped_at_fill": sum(row.get("outcome") != "projected" for row in participant_rows),
                    "paired_cohort_intersection_min": min(sibling_intersections) if sibling_intersections else None,
                    "paired_cohort_intersection_max": max(sibling_intersections) if sibling_intersections else None,
                    "paired_terminal_intersection_min": min(terminal_intersections) if terminal_intersections else None,
                    "paired_terminal_intersection_max": max(terminal_intersections) if terminal_intersections else None,
                    "sample_unit": "unique_shadow_cohort_id; projected sibling accounts are paired, not independent",
                },
                "coverage": {
                    "version_quote_results": int(qstats.get("quote_count") or 0),
                    "version_valid_quotes": int(qstats.get("valid_quoted") or 0),
                    "version_no_route": int(qstats.get("no_route") or 0),
                    "version_quote_errors": int(qstats.get("errors") or 0),
                    "latest_priced_positions": int(account.get("priced_position_count") or 0),
                    "latest_open_positions": int(account.get("open_position_count") or 0),
                    "latest_valuation_status": account.get("valuation_status"),
                },
                "outcomes": {
                    "trades": len(trade_rows),
                    "buy_trades": sum(row["side"] == "BUY" for row in trade_rows),
                    "sell_trades": sum(row["side"] == "SELL" for row in trade_rows),
                    "open": sum(row["status"] == "open" for row in position_rows),
                    "closed": sum(row["status"] == "closed" for row in position_rows),
                    "writeoff": sum(row["status"] == "written_off" for row in position_rows),
                    "total_realized_pnl_usd": sum(terminal_values),
                    "median_terminal_pnl_usd": statistics.median(terminal_values) if terminal_values else None,
                    "trimmed_mean_terminal_pnl_usd": _trimmed_mean(terminal_values),
                    "win_rate": sum(value > 0 for value in terminal_values) / terminal_count if terminal_count else None,
                    "worst_terminal_pnl_usd": min(terminal_values) if terminal_values else None,
                    "p10_terminal_pnl_usd": _percentile(terminal_values, 0.10),
                    "best_terminal_pnl_usd": max(terminal_values) if terminal_values else None,
                    "best_win_concentration": concentration,
                    "time_block_count": len(blocks),
                    "positive_time_block_ratio": positive_block_ratio,
                    "daily_terminal": {
                        day: {"count": daily_counts[day], "wins": daily_wins[day], "pnl_usd": value}
                        for day, value in sorted(daily.items()) if day != "UNKNOWN"
                    },
                    "latest_cash_usd": account.get("cash_usd"),
                },
                "causal_data_validity": (
                    "INVALID" if invalid else "STRICT_FORWARD_VERSIONED; no historical backfill declared"
                ),
                "comparability": (
                    "INVALID_OR_ENGINEERING_CONTAMINATED" if invalid else
                    "PAIRWISE_ONLY_ON_INTERSECTING_COHORTS; do not count projected accounts as independent samples"
                ),
                "evidence_grade": evidence_grade,
                "classification": classification,
                "classification_reason": classification_reason,
                "reusable_component": reusable,
            }
            instances.append(instance)

    family_members = _group(instances, "behavior_contract_hash")
    families: list[dict[str, Any]] = []
    for (fingerprint,), members in family_members.items():
        classes = Counter(str(member["classification"]) for member in members)
        paper = [member for member in members if member["classification"] == PAPER_CANDIDATE]
        shadow = [member for member in members if member["classification"] == SHADOW_CANDIDATE]
        retained_class = PAPER_CANDIDATE if paper else SHADOW_CANDIDATE if shadow else classes.most_common(1)[0][0]
        representative = (paper or shadow or members)[-1]
        canonical = sorted(members, key=lambda item: (item["version_number"], str(item["arm_id"])), reverse=True)[0]
        families.append({
            "canonical_id": f"canonical-{fingerprint}",
            "canonical_strategy_key": canonical["strategy_key"],
            "behavior_contract_hash": fingerprint,
            "member_count": len(members),
            "versions": sorted({member["version"] for member in members}, key=_version_number),
            "arm_ids": sorted({member["arm_id"] for member in members}),
            "entry_family": representative["entry_family"],
            "exit_family": representative["exit_family"],
            "classification_counts": dict(classes),
            "recommended_classification": retained_class,
            "representative_strategy_key": representative["strategy_key"],
            "contract": representative["behavior_contract"],
            "warning": "成员证据按 versioned instance 保留；跨 epoch 不视为独立同分布样本",
        })
    families.sort(key=lambda item: (item["recommended_classification"], item["behavior_contract_hash"]))

    eliminated = {RETIRED_ECONOMIC_FAILURE, RETIRED_ENGINEERING_FAILURE, SUPERSEDED_REUSABLE, INVALID_OR_UNCOMPARABLE}
    tombstones = []
    for instance in instances:
        if instance["classification"] not in eliminated:
            continue
        tombstones.append({
            "strategy_key": instance["strategy_key"],
            "behavior_contract_hash": instance["behavior_contract_hash"],
            "hypothesis": f"{instance['entry_family']} 入场 × {instance['exit_family']} 退出在该冻结合同下可形成有效前向结果",
            "frontier": instance["activation_frontier"],
            "evidence": {
                "terminal_cohorts": instance["samples"]["terminal_cohorts"],
                "total_realized_pnl_usd": instance["outcomes"]["total_realized_pnl_usd"],
                "median_terminal_pnl_usd": instance["outcomes"]["median_terminal_pnl_usd"],
                "trimmed_mean_terminal_pnl_usd": instance["outcomes"]["trimmed_mean_terminal_pnl_usd"],
                "time_block_count": instance["outcomes"]["time_block_count"],
            },
            "failure_type": instance["classification"],
            "root_cause": instance["classification_reason"],
            "reusable_component": instance["reusable_component"],
            "prohibited_repeat": (
                "不得跨执行/成本/终态合同合并 PNL；不得将共享 cohort 投影当独立样本；"
                "工程或因果污染修复前不得宣称策略经济失败/成功"
            ),
        })

    family_by_hash = {family["behavior_contract_hash"]: family for family in families}
    v14_paper = []
    v14_shadow = []
    for family in families:
        members = family_members[(family["behavior_contract_hash"],)]
        eligible = [member for member in members if member["classification"] == family["recommended_classification"]]
        if family["recommended_classification"] not in {PAPER_CANDIDATE, SHADOW_CANDIDATE} or not eligible:
            continue
        representative = sorted(
            eligible,
            key=lambda item: (
                item["evidence_grade"] == "A",
                item["samples"]["terminal_cohorts"],
                item["outcomes"]["total_realized_pnl_usd"],
                item["version_number"],
            ),
            reverse=True,
        )[0]
        candidate = {
            "candidate_id": f"v14-{family['behavior_contract_hash']}",
            "behavior_contract_hash": family["behavior_contract_hash"],
            "mode": "PAPER" if family["recommended_classification"] == PAPER_CANDIDATE else "SHADOW_ONLY",
            "provenance": [member["strategy_key"] for member in members],
            "representative": representative["strategy_key"],
            "reason": representative["classification_reason"],
            "frozen_contract": family["contract"],
            "activation_frontier": "NEW_FRONTIER_REQUIRED_IF_USER_APPROVES_IMPLEMENTATION",
            "live_execution": False,
        }
        (v14_paper if candidate["mode"] == "PAPER" else v14_shadow).append(candidate)

    classifications = Counter(instance["classification"] for instance in instances)
    v13_rows = [instance for instance in instances if instance["version_number"] == 13]
    terminal_total = sum(instance["samples"]["terminal_cohorts"] for instance in instances)
    valid_positive = [
        instance for instance in instances
        if instance["classification"] not in {
            RETIRED_ENGINEERING_FAILURE, INVALID_OR_UNCOMPARABLE,
        }
        and instance["outcomes"]["total_realized_pnl_usd"] > 0
    ]
    report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "database": str(database),
            "read_only": True,
            "scope": "v1-v13 historical strategy universe; no new computation/backtest",
            "live_execution": False,
        },
        "summary": {
            "theoretical_version_count": EXPECTED_VERSION_COUNT,
            "actual_version_count": len(registrations),
            "theoretical_instances_if_12_each": EXPECTED_INSTANCE_COUNT,
            "actual_enumerated_instances": len(instances),
            "missing_instances": EXPECTED_INSTANCE_COUNT - len(instances),
            "unique_arm_ids": len({instance["arm_id"] for instance in instances}),
            "behavior_contract_families": len(families),
            "classification_counts": dict(classifications),
            "paper_candidate_count": len(v14_paper),
            "shadow_candidate_count": len(v14_shadow),
            "tombstone_count": len(tombstones),
            "recommend_v14_implementation": bool(v14_paper or v14_shadow),
            "recommendation": (
                "先由用户审阅候选与失败墓碑；本报告不注册、不激活 v14。"
                + ("当前没有达到 Paper 晋级门槛的策略。" if not v14_paper else "存在通过严格门槛的 Paper 候选。")
            ),
        },
        "methodology": {
            "classification_is_mutually_exclusive": True,
            "paper_gate": "terminal cohorts >=30; total, median and 10% trimmed mean >0; >=50% positive time blocks; best-win concentration <=75%; no engineering/causal invalidation",
            "economic_failure_gate": "terminal cohorts >=30 and total, median, trimmed mean all <=0 under a causally valid contract",
            "insufficient_rule": "missing coverage or insufficient terminal/time-block evidence is not success or economic failure",
            "paired_rule": "shared-cohort projected accounts are paired observations; exit comparisons require intersecting participated cohorts",
            "unknown_rule": "UNKNOWN/no-route is retained as missing/coverage evidence unless the frozen terminal contract supplies independent structural proof",
            "no_future_data": "only immutable versioned DB rows produced after each registration/frontier are summarized; no history is reclassified as a new trade and no backtest/search is run",
        },
        "executive_summary": {
            "economic_conclusion": (
                "当前没有任何历史行为合同同时满足因果有效、足够终局样本、"
                "跨时间块稳定、扣摩擦总计/中位数/截尾均值为正且不过度依赖单一赢家；"
                "因此 v14 Paper 候选必须为空。"
            ),
            "current_v13": {
                "strategy_instances": len(v13_rows),
                "terminal_cohorts_projected_sum": sum(
                    row["samples"]["terminal_cohorts"] for row in v13_rows
                ),
                "realized_pnl_projected_sum_usd": sum(
                    row["outcomes"]["total_realized_pnl_usd"] for row in v13_rows
                ),
                "warning": "投影和仅描述 12 个账户账本，不等于独立 cohort 数或组合可交易收益。",
            },
            "all_versions_terminal_cohorts_projected_sum": terminal_total,
            "valid_positive_instance_count": len(valid_positive),
            "most_important_successes": [
                "v11 将资本资格改为每策略账户独立，消除了最弱账户共享现金 veto。",
                "v12/v13 将高频估值从持续 Jupiter 请求转向 DexScreener 市场标记，并保留 UNKNOWN 不按 0 处理。",
                "v1–v13 均声明 no_historical_backfill，版本/frontier 可用于严格区分历史 epoch。",
                "这些是可复用工程/实验组件，不是已验证 alpha。",
            ],
            "most_important_failures": [
                "v6 负现金、v7 调度干扰、v10 最弱账户现金 veto 属于工程失败，不能据此评价策略经济性。",
                "v8 将本池容量提升为终态、v9 将单一 no-route 直接核销，属于终态语义污染。",
                "v11 持续 Jupiter 估值和 v12 Jupiter BUY 依赖限制了覆盖，已被后续合同替代。",
                "v13 当前没有 Paper 级获利证据；成熟且稳健为负的策略不能在 v14 中复活。",
            ],
            "remaining_evidence_gaps": [
                "v1/v2 没有终局样本，v3/v4 时间块与样本不足。",
                "多个 flow_burst/reawakening 账户尚无足够自然前向参与和终局分母。",
                "退出策略的有效比较仍需基于相同 entry family 的实际共同参与 cohort 交集。",
                "当前历史没有任何策略达到跨时间块、稳健统计和集中度联合晋级门。",
            ],
            "next_decision": "用户先审阅本报告；若接受，下一阶段只注册 v14 Shadow 候选或继续收集 v13，不自动激活 Paper/Live。",
        },
        "instances": instances,
        "behavior_families": families,
        "failure_tombstones": tombstones,
        "v14_draft": {
            "status": "DRAFT_ONLY_NOT_REGISTERED_NOT_ACTIVE",
            "paper_candidates": v14_paper,
            "shadow_candidates": v14_shadow,
            "rule": "no invented parameters; exact frozen contracts with provenance only",
        },
    }
    validate_report(report)
    return report


def build_daily_learning_report(report: dict[str, Any], report_day: str | None = None) -> dict[str, Any]:
    day = report_day or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    today_rows = []
    for instance in report["instances"]:
        daily = instance["outcomes"].get("daily_terminal", {}).get(day, {})
        today_rows.append({
            "strategy_key": instance["strategy_key"],
            "canonical_id": f"canonical-{instance['behavior_contract_hash']}",
            "version": instance["version"],
            "arm_id": instance["arm_id"],
            "name": instance["name"],
            "entry_family": instance["entry_family"],
            "exit_family": instance["exit_family"],
            "classification": instance["classification"],
            "evidence_grade": instance["evidence_grade"],
            "today_terminal_count": int(daily.get("count") or 0),
            "today_win_count": int(daily.get("wins") or 0),
            "today_realized_pnl_usd": float(daily.get("pnl_usd") or 0.0),
            "total_terminal_cohorts": instance["samples"]["terminal_cohorts"],
            "total_realized_pnl_usd": instance["outcomes"]["total_realized_pnl_usd"],
            "median_terminal_pnl_usd": instance["outcomes"]["median_terminal_pnl_usd"],
            "trimmed_mean_terminal_pnl_usd": instance["outcomes"]["trimmed_mean_terminal_pnl_usd"],
            "tail_p10_usd": instance["outcomes"]["p10_terminal_pnl_usd"],
            "win_rate": instance["outcomes"]["win_rate"],
            "time_block_count": instance["outcomes"]["time_block_count"],
            "positive_time_block_ratio": instance["outcomes"]["positive_time_block_ratio"],
            "best_win_concentration": instance["outcomes"]["best_win_concentration"],
            "explanation_zh": instance["classification_reason"],
            "action": (
                "人工审阅后才可晋级 Paper" if instance["classification"] == PAPER_CANDIDATE else
                "继续 Shadow 收集证据" if instance["classification"] == SHADOW_CANDIDATE else
                "停止未来计算，保留墓碑与可复用组件"
            ),
        })
    active = [row for row in today_rows if "/v13-" in row["version"]]
    negative_pending = [
        row for row in active
        if row["classification"] == SHADOW_CANDIDATE
        and row["total_terminal_cohorts"] > 0
        and row["total_realized_pnl_usd"] < 0
    ]
    coverage_gap = [
        row for row in active
        if row["classification"] == SHADOW_CANDIDATE
        and row["total_terminal_cohorts"] == 0
    ]
    family_counts = Counter(family["recommended_classification"] for family in report["behavior_families"])
    daily = {
        "report_version": "chain-meme-trader-daily-learning/v1",
        "report_day_asia_shanghai": day,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "READ_ONLY_EVALUATION_SELECTION",
        "strategy_universe": {
            "versioned_instances": len(report["instances"]),
            "canonical_contracts": len(report["behavior_families"]),
            "canonical_identity_rule": "one canonical identity per full behavior contract; all versioned evidence and lineage retained",
            "canonical_status_counts": dict(family_counts),
        },
        "fairness_and_data_health": {
            "as_of_only": True,
            "future_data_forbidden": True,
            "execution_rule": "next-quote or frozen version-specific next observable execution contract",
            "shared_market_data": True,
            "duplicate_external_market_requests_per_strategy": False,
            "paired_comparison_rule": "exit policies compare only on intersecting actually-participated cohorts",
            "engineering_or_data_failure_can_cause_economic_retirement": False,
            "paper_promotion_requires_human_confirmation": True,
            "live_binding_requires_human_confirmation": True,
        },
        "today_performance": {
            "terminal_count": sum(row["today_terminal_count"] for row in today_rows),
            "win_count": sum(row["today_win_count"] for row in today_rows),
            "realized_pnl_usd_projected_accounts": sum(row["today_realized_pnl_usd"] for row in today_rows),
            "warning": "账户投影合计不是独立样本收益；策略比较仍使用共同 cohort。",
            "strategies": today_rows,
        },
        "failure_attribution": {
            "classification_counts": report["summary"]["classification_counts"],
            "categories": {
                "economic": "仅在因果/工程有效且终局、稳健指标、时间块充分时判定",
                "engineering": "账户、调度、执行实现故障；样本无效，不据此淘汰经济假设",
                "data_quality": "终态或 no-route 语义污染；保留原始证据但不参与经济排名",
                "coverage_insufficient": "没有足够自然前向样本；不是成功也不是失败",
                "superseded_or_duplicate": "旧合同/等价迁移由 canonical identity 归纳，lineage 不删除",
                "invalid_uncomparable": "因果污染或执行合同不可比",
            },
        },
        "learned_components": report["executive_summary"]["most_important_successes"],
        "new_challengers": [],
        "selection": {
            "paper_candidates": report["v14_draft"]["paper_candidates"],
            "shadow_candidates": report["v14_draft"]["shadow_candidates"],
            "negative_pending_confirmation": negative_pending,
            "coverage_gap_untested": coverage_gap,
            "retirement_tombstone_count": len(report["failure_tombstones"]),
            "automatic_online_logic_change": False,
        },
        "tomorrow_plan": [
            "继续共享一次行情采集，不按策略重复请求外部数据。",
            "为 broad_launch 负向待确认策略补足严格前向终局与时间块，不提前判胜。",
            "为 flow_burst/reawakening 恢复自然前向覆盖；零样本保持未测试。",
            "任何新候选仅进入 Shadow；Paper 晋级和 Live 绑定等待人工确认。",
        ],
    }
    assert len(negative_pending) == 3, "expected three v13 broad-launch negative-pending strategies"
    assert len(coverage_gap) == 8, "expected eight v13 flow/reawakening coverage gaps"
    return daily


def render_daily_html(daily: dict[str, Any]) -> str:
    payload = _json(daily).replace("</", "<\\/")
    return f"""<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>ChainMemeTrader 每日学习报告</title><style>body{{margin:0;background:#07101b;color:#eaf3f7;font:14px/1.6 Segoe UI,sans-serif}}main{{width:min(1200px,calc(100% - 32px));margin:auto;padding:32px}}section{{margin:14px 0;padding:18px;border:1px solid #263d4c;border-radius:14px;background:#0e1b27}}h1{{font-size:38px}}h2{{color:#78e7e0}}.warn{{color:#ffc96f}}.bad{{color:#ff807a}}.learn{{color:#bb9cff}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #263d4c;text-align:left}}th{{color:#8fa9b8}}code{{color:#78e7e0}}</style></head><body><main><p><code>{html.escape(daily['report_version'])}</code></p><h1>{html.escape(daily['report_day_asia_shanghai'])} 每日学习报告</h1><section><h2>公平性 / 数据健康</h2><p>严格 as-of；禁止未来数据；共享行情一次采集；同入场退出只在实际共同 cohort 上成对比较。工程或数据故障不会触发经济淘汰。</p></section><section><h2>今日表现</h2><p>终局 {daily['today_performance']['terminal_count']} · 胜 {daily['today_performance']['win_count']} · 投影账户已实现 PNL {_fmt(daily['today_performance']['realized_pnl_usd_projected_accounts'])}</p><p class=\"warn\">{html.escape(daily['today_performance']['warning'])}</p></section><section><h2>失败归因</h2><div id=\"failures\"></div></section><section><h2>学习到的组件</h2><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in daily['learned_components'])}</ul></section><section><h2>新 Challenger</h2><p class=\"learn\">本日没有自动创建 Challenger。任何新候选只能先进入 Shadow，并等待人工确认。</p></section><section><h2>Shadow 去向</h2><p>负向待确认 {len(daily['selection']['negative_pending_confirmation'])}；覆盖缺口/未测试 {len(daily['selection']['coverage_gap_untested'])}；历史墓碑 {daily['selection']['retirement_tombstone_count']}。</p><div id=\"shadow\"></div></section><section><h2>明日计划</h2><ol>{''.join(f'<li>{html.escape(x)}</li>' for x in daily['tomorrow_plan'])}</ol></section><script id=\"payload\" type=\"application/json\">{payload}</script><script>const d=JSON.parse(document.getElementById('payload').textContent),e=v=>String(v??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}}[c]));document.getElementById('failures').innerHTML=Object.entries(d.failure_attribution.categories).map(([k,v])=>`<p><strong>${{e(k)}}</strong> · ${{e(v)}}</p>`).join('');const rows=[...d.selection.negative_pending_confirmation,...d.selection.coverage_gap_untested];document.getElementById('shadow').innerHTML=`<table><thead><tr><th>策略</th><th>状态</th><th>终局</th><th>总 PNL</th><th>解释</th></tr></thead><tbody>${{rows.map(x=>`<tr><td>${{e(x.arm_id)}}</td><td>${{x.total_terminal_cohorts?'负向待确认':'覆盖缺口/未测试'}}</td><td>${{x.total_terminal_cohorts}}</td><td>${{Number(x.total_realized_pnl_usd).toFixed(2)}}</td><td>${{e(x.explanation_zh)}}</td></tr>`).join('')}}</tbody></table>`;</script></main></body></html>"""


def validate_report(report: dict[str, Any]) -> None:
    instances = report["instances"]
    assert report["summary"]["actual_version_count"] == EXPECTED_VERSION_COUNT
    counts = Counter(instance["version"] for instance in instances)
    assert len(counts) == EXPECTED_VERSION_COUNT
    assert set(counts.values()) == {EXPECTED_POLICIES_PER_VERSION}
    assert len(instances) == EXPECTED_INSTANCE_COUNT
    allowed = {
        PAPER_CANDIDATE, SHADOW_CANDIDATE, RETIRED_ECONOMIC_FAILURE,
        RETIRED_ENGINEERING_FAILURE, SUPERSEDED_REUSABLE, INVALID_OR_UNCOMPARABLE,
    }
    assert all(instance["classification"] in allowed for instance in instances)
    tombstone_keys = {item["strategy_key"] for item in report["failure_tombstones"]}
    assert all(
        instance["strategy_key"] in tombstone_keys
        for instance in instances
        if instance["classification"] in {
            RETIRED_ECONOMIC_FAILURE, RETIRED_ENGINEERING_FAILURE,
            SUPERSEDED_REUSABLE, INVALID_OR_UNCOMPARABLE,
        }
    )
    for candidate in report["v14_draft"]["paper_candidates"] + report["v14_draft"]["shadow_candidates"]:
        assert candidate["provenance"] and candidate["frozen_contract"]
        assert candidate["live_execution"] is False


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_html(report: dict[str, Any]) -> str:
    payload = _json(report).replace("</", "<\\/")
    summary = report["summary"]
    counts = summary["classification_counts"]
    cards = "".join(
        f'<article><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></article>'
        for label, value in [
            ("版本", summary["actual_version_count"]),
            ("版本化策略", summary["actual_enumerated_instances"]),
            ("行为合同族", summary["behavior_contract_families"]),
            ("Paper 候选", summary["paper_candidate_count"]),
            ("Shadow 候选", summary["shadow_candidate_count"]),
            ("失败墓碑", summary["tombstone_count"]),
        ]
    )
    return f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>ChainMemeTrader v1-v13 历史策略全集</title>
<style>
:root{{--bg:#07100e;--panel:#0f1d19;--line:#294039;--text:#e9f5f0;--muted:#91aaa0;--mint:#75efbf;--red:#ff827b;--amber:#ffd174}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 90% 0,#17372c 0,transparent 34rem),var(--bg);color:var(--text);font:14px/1.5 Inter,Segoe UI,sans-serif}}main{{width:min(1800px,calc(100% - 32px));margin:auto;padding:32px 0 80px}}h1{{font-size:clamp(30px,5vw,58px);letter-spacing:-.05em;margin:.2em 0}}h2{{margin:0 0 12px}}p{{color:var(--muted)}}.eyebrow{{font:700 11px ui-monospace;color:var(--mint);letter-spacing:.14em}}.cards{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin:22px 0}}article,.panel{{border:1px solid var(--line);background:rgba(15,29,25,.93);border-radius:14px;padding:15px}}article span{{display:block;color:var(--muted);font-size:11px}}article strong{{font-size:24px}}.panel{{margin:14px 0}}.controls{{display:grid;grid-template-columns:1.5fr repeat(3,minmax(150px,.5fr));gap:8px;margin:12px 0}}input,select{{width:100%;background:#091512;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:10px}}.table{{overflow:auto;max-height:70vh;border:1px solid var(--line);border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1700px}}th,td{{padding:9px 10px;border-bottom:1px solid #20332d;white-space:nowrap;text-align:left}}th{{position:sticky;top:0;background:#12251f;color:var(--muted);z-index:2;font-size:10px}}td small{{display:block;color:var(--muted)}}.pill{{display:inline-block;padding:3px 7px;border-radius:999px;background:#17372d;color:var(--mint);font-size:10px}}.bad{{color:var(--red)}}.warn{{color:var(--amber)}}.candidate{{color:var(--mint)}}details{{border-top:1px solid var(--line);padding:10px 0}}summary{{cursor:pointer;font-weight:700}}code{{color:var(--mint)}}.note{{padding:12px;border-left:3px solid var(--amber);background:#141d17}}@media(max-width:1000px){{.cards{{grid-template-columns:repeat(2,1fr)}}.controls{{grid-template-columns:1fr}}}}
</style></head><body><main>
<p class=\"eyebrow\">READ-ONLY · STRICT FORWARD · GENERATED FROM SQLITE</p><h1>v1–v13 历史策略全集与 v14 候选</h1>
<p>先保留 156 条 <code>definition_version × arm_id</code> 独立证据，再按完整交易合同归纳。报告没有注册或激活 v14，没有运行回测、参数搜索或真实交易。</p>
<section class=\"cards\">{cards}</section>
<section class=\"panel\"><h2>执行摘要</h2><p>{html.escape(summary['recommendation'])}</p><div id=\"classCounts\"></div><div id=\"executive\"></div><p class=\"note\">排名单位不是“12 个投影账户 = 12 个独立样本”。共享 cohort 的退出策略必须在共同参与的 cohort 交集上成对比较；工程 PASS、单个总 PNL、UNKNOWN/no-route 都不能单独证明盈利或失败。</p></section>
<section class=\"panel\"><h2>v14 候选草案</h2><p><strong>尚未注册、尚未激活、Live=false。</strong> Paper 只接收通过严格多指标门的历史合同；其余有潜力者仅 Shadow。</p><div id=\"candidates\"></div></section>
<section class=\"panel\"><h2>156 条 Historical Strategy Universe</h2><div class=\"controls\"><input id=\"search\" placeholder=\"搜索 version / arm / family / 原因\"><select id=\"version\"><option value=\"\">全部版本</option></select><select id=\"classification\"><option value=\"\">全部分类</option></select><select id=\"sort\"><option value=\"version\">按版本</option><option value=\"pnl_desc\">PNL 高到低</option><option value=\"terminal_desc\">终局样本多到少</option></select></div><p id=\"visibleCount\"></p><div class=\"table\"><table><thead><tr><th>版本</th><th>Arm / 行为族</th><th>入场</th><th>退出</th><th>分类</th><th>等级</th><th>决策/准入</th><th>参与/成对终局</th><th>交易 B/S</th><th>开/平/核销</th><th>总 PNL</th><th>中位数</th><th>截尾均值</th><th>胜率</th><th>P10 / 最差</th><th>赢家集中度</th><th>时间块</th><th>估值覆盖</th><th>停止/替代理由</th></tr></thead><tbody id=\"universe\"></tbody></table></div></section>
<section class=\"panel\"><h2>跨版本完整行为合同族</h2><p>指纹包含入场、退出、资本资格、报价/成交来源、成本、估值、no-route 与 terminal 语义；版本化证据仍逐条保留。</p><div class=\"table\"><table><thead><tr><th>合同族</th><th>成员</th><th>版本</th><th>Arm</th><th>入场/退出</th><th>建议分类</th><th>成员分类</th></tr></thead><tbody id=\"families\"></tbody></table></div></section>
<section class=\"panel\"><h2>失败墓碑</h2><p>被淘汰或替代的策略不会删除；墓碑记录失败类型、证据、可复用部分与禁止重复的坑。</p><div id=\"tombstones\"></div></section>
<section class=\"panel\"><h2>判定方法</h2><pre id=\"method\"></pre></section>
<script id=\"payload\" type=\"application/json\">{payload}</script><script>
const data=JSON.parse(document.getElementById('payload').textContent), fmt=v=>v==null?'—':typeof v==='number'?v.toFixed(2):v, pct=v=>v==null?'—':(v*100).toFixed(1)+'%', esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}}[c]));
document.getElementById('classCounts').innerHTML=Object.entries(data.summary.classification_counts).map(([k,v])=>`<span class=\"pill\">${{esc(k)}} ${{v}}</span> `).join('');
const ex=data.executive_summary;document.getElementById('executive').innerHTML=`<h3>经济结论</h3><p>${{esc(ex.economic_conclusion)}}</p><div class=\"cards\"><article><span>v13 策略实例</span><strong>${{ex.current_v13.strategy_instances}}</strong></article><article><span>v13 投影终局合计</span><strong>${{ex.current_v13.terminal_cohorts_projected_sum}}</strong></article><article><span>v13 投影已实现 PNL</span><strong>${{fmt(ex.current_v13.realized_pnl_projected_sum_usd)}}</strong></article><article><span>有效正向实例</span><strong>${{ex.valid_positive_instance_count}}</strong></article></div><p class=\"warn\">${{esc(ex.current_v13.warning)}}</p><h3>最重要的成功经验（不是 alpha）</h3><ul>${{ex.most_important_successes.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul><h3>最重要失败教训</h3><ul>${{ex.most_important_failures.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul><h3>仍缺证据</h3><ul>${{ex.remaining_evidence_gaps.map(x=>`<li>${{esc(x)}}</li>`).join('')}}</ul><p><strong>下一决策：</strong>${{esc(ex.next_decision)}}</p>`;
const cand=data.v14_draft; document.getElementById('candidates').innerHTML=`<h3>Paper (${{cand.paper_candidates.length}})</h3>${{cand.paper_candidates.length?cand.paper_candidates.map(x=>`<p class=\"candidate\"><strong>${{esc(x.candidate_id)}}</strong> · ${{esc(x.representative)}} · ${{esc(x.reason)}}</p>`).join(''):'<p class=\"warn\">空集：没有历史策略达到 Paper 晋级门槛。</p>'}}<h3>Shadow (${{cand.shadow_candidates.length}})</h3>${{cand.shadow_candidates.map(x=>`<details><summary>${{esc(x.candidate_id)}} · ${{esc(x.representative)}}</summary><p>${{esc(x.reason)}}</p><small>provenance: ${{esc(x.provenance.join(' · '))}}</small></details>`).join('')||'<p>空集</p>'}}`;
const versions=[...new Set(data.instances.map(x=>x.version))]; document.getElementById('version').innerHTML+=[...versions].map(x=>`<option>${{esc(x)}}</option>`).join(''); const classes=Object.keys(data.summary.classification_counts);document.getElementById('classification').innerHTML+=classes.map(x=>`<option>${{esc(x)}}</option>`).join('');
function draw(){{let rows=[...data.instances],q=document.getElementById('search').value.toLowerCase(),v=document.getElementById('version').value,c=document.getElementById('classification').value,s=document.getElementById('sort').value;rows=rows.filter(x=>(!v||x.version===v)&&(!c||x.classification===c)&&(!q||JSON.stringify([x.version,x.arm_id,x.entry_family,x.exit_family,x.classification,x.stop_reason]).toLowerCase().includes(q)));if(s==='pnl_desc')rows.sort((a,b)=>b.outcomes.total_realized_pnl_usd-a.outcomes.total_realized_pnl_usd);else if(s==='terminal_desc')rows.sort((a,b)=>b.samples.terminal_cohorts-a.samples.terminal_cohorts);else rows.sort((a,b)=>a.version_number-b.version_number||String(a.arm_id).localeCompare(String(b.arm_id)));document.getElementById('visibleCount').textContent=`显示 ${{rows.length}} / ${{data.instances.length}} 条`;document.getElementById('universe').innerHTML=rows.map(x=>`<tr><td>v${{x.version_number}}<small>${{esc(x.version)}}</small></td><td><strong>${{esc(x.arm_id)}}</strong><small>${{esc(x.behavior_contract_hash)}}</small></td><td>${{esc(x.entry_family)}}</td><td>${{esc(x.exit_family)}}</td><td><span class=\"pill\">${{esc(x.classification)}}</span><small>${{esc(x.classification_reason)}}</small></td><td>${{esc(x.evidence_grade)}}</td><td>${{x.samples.decisions}} / ${{x.samples.admitted_decisions}}</td><td>${{x.samples.participated_cohorts}} / ${{fmt(x.samples.paired_terminal_intersection_min)}}</td><td>${{x.outcomes.buy_trades}} / ${{x.outcomes.sell_trades}}</td><td>${{x.outcomes.open}} / ${{x.outcomes.closed}} / ${{x.outcomes.writeoff}}</td><td>${{fmt(x.outcomes.total_realized_pnl_usd)}}</td><td>${{fmt(x.outcomes.median_terminal_pnl_usd)}}</td><td>${{fmt(x.outcomes.trimmed_mean_terminal_pnl_usd)}}</td><td>${{pct(x.outcomes.win_rate)}}</td><td>${{fmt(x.outcomes.p10_terminal_pnl_usd)}} / ${{fmt(x.outcomes.worst_terminal_pnl_usd)}}</td><td>${{pct(x.outcomes.best_win_concentration)}}</td><td>${{x.outcomes.time_block_count}} / ${{pct(x.outcomes.positive_time_block_ratio)}}</td><td>${{x.coverage.latest_priced_positions}} / ${{x.coverage.latest_open_positions}}<small>${{esc(x.coverage.latest_valuation_status)}}</small></td><td>${{esc(x.stop_reason)}}</td></tr>`).join('')}}
['search','version','classification','sort'].forEach(id=>document.getElementById(id).addEventListener(id==='search'?'input':'change',draw));draw();
document.getElementById('families').innerHTML=data.behavior_families.map(x=>`<tr><td><code>${{esc(x.behavior_contract_hash)}}</code></td><td>${{x.member_count}}</td><td>${{esc(x.versions.map(v=>'v'+v.split('/v')[1].split('-')[0]).join(', '))}}</td><td>${{esc(x.arm_ids.join(', '))}}</td><td>${{esc(x.entry_family)}} / ${{esc(x.exit_family)}}</td><td>${{esc(x.recommended_classification)}}</td><td>${{esc(JSON.stringify(x.classification_counts))}}</td></tr>`).join('');
document.getElementById('tombstones').innerHTML=data.failure_tombstones.map(x=>`<details><summary>${{esc(x.failure_type)}} · ${{esc(x.strategy_key)}}</summary><p><strong>根因：</strong>${{esc(x.root_cause)}}<br><strong>证据：</strong>${{esc(JSON.stringify(x.evidence))}}<br><strong>可复用：</strong>${{esc(x.reusable_component)}}<br><strong>禁止重复：</strong>${{esc(x.prohibited_repeat)}}</p></details>`).join('');document.getElementById('method').textContent=JSON.stringify(data.methodology,null,2);
</script></main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("data/memetrader_forward_20260830_r6.sqlite3"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/PROJECT_CONTEXT"))
    args = parser.parse_args()
    report = build_report(args.database.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json"
    html_path = args.output_dir / "CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.html"
    daily_json_path = args.output_dir / "CHAIN_MEME_TRADER_DAILY_LEARNING_REPORT_LATEST.json"
    daily_html_path = args.output_dir / "CHAIN_MEME_TRADER_DAILY_LEARNING_REPORT_LATEST.html"
    daily = build_daily_learning_report(report)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    daily_json_path.write_text(json.dumps(daily, ensure_ascii=False, indent=2), encoding="utf-8")
    daily_html_path.write_text(render_daily_html(daily), encoding="utf-8")
    print(json.dumps({"json": str(json_path.resolve()), "html": str(html_path.resolve()), "daily_json": str(daily_json_path.resolve()), "daily_html": str(daily_html_path.resolve()), **report["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
