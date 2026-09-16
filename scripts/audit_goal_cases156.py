"""Bounded, read-only extension of righttail152 to every goal-supplied address.

Never an entry allow-list. No network calls, strategy mutations or peak-price
backfill. All canonical chain matches remain separate. Histories exceeding the
sample budget are marked incomplete, not silently reported as zero.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sqlite3
import time

from audit_user_righttail152 import ADDRESSES

ROOT = Path(__file__).resolve().parents[1]


def addresses_from_text(text):
    found = []
    for line in text.splitlines():
        # Goal attachments encode leading spaces as HTML entities. Decode the
        # line before applying the standalone-address rule; do not search
        # arbitrary prose for address-looking substrings.
        value = html.unescape(line).strip()
        if re.fullmatch(r"0x[0-9a-fA-F]{20,64}", value):
            value = value.lower()
        elif not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", value):
            continue
        if value not in found:
            found.append(value)
    return found


def candidate_ids(address):
    if address.startswith('0x'):
        return [chain + ':' + address.lower() for chain in ('bsc', 'robinhood')]
    return ['solana:' + address]


def stamp(value):
    try:
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value.timestamp() if value.tzinfo is not None else None
    except (AttributeError, ValueError):
        return None


def reported_event_stamp(value):
    """Provider pairCreatedAt may be Unix milliseconds; it is not a local receipt."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = value / 1000 if value > 1e11 else value
        return seconds if math.isfinite(seconds) and seconds > 0 else None
    return stamp(value)


def creation_discovery_timeline(token, exposures, launches, snapshots, cutoff):
    valid_exposures = [row for row in exposures
        if (observed := stamp(row.get('observed_at'))) is not None
        and (recorded := stamp(row.get('recorded_at'))) is not None
        and observed <= recorded <= cutoff]
    valid_exposures.sort(key=lambda row: (stamp(row['recorded_at']), row['id']))
    valid_launches = [row for row in launches
        if (source := stamp(row.get('source_observed_at'))) is not None
        and (ingested := stamp(row.get('ingested_at'))) is not None
        and (recorded := stamp(row.get('recorded_at'))) is not None
        and source <= ingested <= recorded <= cutoff]
    valid_launches.sort(key=lambda row: (stamp(row['recorded_at']), row['id']))
    pair_evidence = []
    for row in snapshots:
        observed = stamp(row.get('observed_at'))
        recorded = stamp(row.get('recorded_at'))
        created = reported_event_stamp(row.get('pair_created_at'))
        if (not row.get('pair_address') or observed is None or recorded is None
                or created is None or not created <= observed <= recorded <= cutoff):
            continue
        pair_evidence.append({
            'pair_address': row['pair_address'],
            'reported_pair_created_at': datetime.fromtimestamp(created, timezone.utc).isoformat(),
            'first_locally_observed_at': row['observed_at'],
            'first_locally_recorded_at': row['recorded_at'],
            'provider': row.get('provider'),
        })
    pair_evidence.sort(key=lambda row: (stamp(row['first_locally_recorded_at']),
                                            row['pair_address']))
    first_local = next((row for row in valid_exposures
                        if row.get('first_local_discovery')), None)
    token_created = token.get('created_at')
    return {
        'database_token_created_at': token_created if stamp(token_created) is not None
            and stamp(token_created) <= cutoff else None,
        'valid_exposure_count': len(valid_exposures),
        'invalid_or_future_exposure_count': len(exposures) - len(valid_exposures),
        'first_exposure': valid_exposures[0] if valid_exposures else None,
        'first_local_discovery_exposure': first_local,
        'valid_launch_fact_count': len(valid_launches),
        'invalid_or_future_launch_fact_count': len(launches) - len(valid_launches),
        'first_launch_fact': valid_launches[0] if valid_launches else None,
        'first_reported_pair_creation': pair_evidence[0] if pair_evidence else None,
        'creation_clock_status': 'stored_launch_fact' if valid_launches else 'launch_source_clock_unknown',
    }


def quantiles(values):
    values = sorted(values)
    return {name: values[round((len(values)-1)*p)] if values else None
            for name, p in [('p50', .5), ('p90', .9), ('p99', .99)]}


def asof_rows(rows, field, cutoff):
    """Do not let malformed/future event clocks masquerade as as-of evidence."""
    return [row for row in rows if (value := stamp(row.get(field))) is not None and value <= cutoff]


def snapshot_summary(rows, cutoff):
    pools = defaultdict(dict)
    invalid = Counter()
    processing = []
    first_valid = None
    for row in rows:
        observed, recorded = stamp(row['observed_at']), stamp(row['recorded_at'])
        pair = row['pair_address']
        if pair and pair.startswith('0x'):
            pair = pair.lower()
        price, liquidity = row['price_usd'], row['liquidity_usd']
        if observed is None or recorded is None or not observed <= recorded <= cutoff:
            invalid['causal_time_invalid'] += 1
            continue
        if recorded-observed > 15:
            invalid['stale_at_ingestion'] += 1
            continue
        if not pair:
            invalid['pool_unknown'] += 1
            continue
        if not isinstance(price, (float, int)) or not math.isfinite(price) or price <= 0:
            invalid['price_invalid'] += 1
            continue
        if not isinstance(liquidity, (int, float)) or not math.isfinite(liquidity) or liquidity < 0:
            invalid['liquidity_unknown_or_invalid'] += 1
            continue
        # Same-time replays are one observation, not evidence of fresh sampling.
        pools[pair].setdefault(observed, row['id'])
        processing.append(recorded - observed)
        if first_valid is None or (recorded, row['id']) < (
                stamp(first_valid['recorded_at']), first_valid['snapshot_id']):
            pair_created = reported_event_stamp(row.get('pair_created_at'))
            first_valid = dict(snapshot_id=row['id'], pair_address=pair,
                provider=row.get('provider'), observed_at=row['observed_at'],
                recorded_at=row['recorded_at'],
                reported_pair_created_at=(
                    datetime.fromtimestamp(pair_created, timezone.utc).isoformat()
                    if pair_created is not None and pair_created <= observed else None))
    result = []
    for pair, observations in pools.items():
        times = sorted(observations)
        gaps = [b-a for a, b in zip(times, times[1:])]
        result.append(dict(pool=pair, distinct_observations=len(times),
            first_observed_at=datetime.fromtimestamp(times[0], timezone.utc).isoformat(),
            last_observed_at=datetime.fromtimestamp(times[-1], timezone.utc).isoformat(),
            adjacent_gaps_seconds=quantiles(gaps), max_gap_seconds=max(gaps, default=None)))
    return dict(pools=result, first_valid_recorded_pool_snapshot=first_valid,
                invalid_rows=dict(invalid),
                observed_to_recorded_seconds=quantiles(processing))


def audit(connection, addresses, version, *, row_limit=3000, seconds=30):
    deadline = time.monotonic() + seconds
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    cutoff = datetime.now(timezone.utc)

    def rows(sql, args=()):
        return [dict(x) for x in connection.execute(sql, args)]

    results = []
    for address in addresses:
        matches = []
        for token_id in candidate_ids(address):
            matches += rows('SELECT token_id,chain,address,name,symbol,source,created_at,first_seen_at,last_seen_at '
                            'FROM tokens WHERE token_id=?', (token_id,))
        result = dict(address=address, original_15=address in ADDRESSES, matches=[],
            address_validation=('invalid_evm_length' if address.startswith('0x') and len(address) != 42
                                else 'syntax_only_not_chain_existence'))
        for token in matches:
            token_id = token['token_id']
            item = dict(token=token)
            result['matches'].append(item)
            try:
                item['excluded_invalid_or_future_time'] = {}

                def causal(values, field, label):
                    valid = asof_rows(values, field, cutoff.timestamp())
                    item['excluded_invalid_or_future_time'][label] = len(values) - len(valid)
                    return valid

                # All large histories use token/source/cohort index prefixes.
                snapshots = rows("SELECT id,observed_at,recorded_at,provider,price_usd,liquidity_usd,"
                    "COALESCE(json_extract(raw_json,'$.pair.pairAddress'),"
                    "json_extract(raw_json,'$.pairAddress')) pair_address,"
                    "COALESCE(json_extract(raw_json,'$.pair.pairCreatedAt'),"
                    "json_extract(raw_json,'$.pairCreatedAt')) pair_created_at FROM token_snapshots "
                    "WHERE token_id=? ORDER BY observed_at,id LIMIT ?", (token_id, row_limit+1))
                item['snapshot_history_truncated'] = len(snapshots) > row_limit
                snapshots = snapshots[:row_limit]
                item['sampled_snapshot_count'] = len(snapshots)
                item['sampled_snapshot_time_range'] = [snapshots[0]['observed_at'], snapshots[-1]['observed_at']] if snapshots else []
                item['market_observations'] = snapshot_summary(snapshots, cutoff.timestamp())
                exposures = rows('SELECT e.id,e.round_id,e.role,e.first_local_discovery,'
                    'e.no_pair,e.observed_at,e.recorded_at,r.provider,r.surface,r.mode,'
                    'r.status round_status,r.started_at round_started_at,'
                    'r.completed_at round_completed_at FROM token_discovery_exposures e '
                    'JOIN token_discovery_rounds r ON r.id=e.round_id '
                    'WHERE e.token_id=? ORDER BY e.observed_at,e.id LIMIT ?',
                    (token_id, row_limit+1))
                item['discovery_history_truncated'] = len(exposures) > row_limit
                launches = rows('SELECT id,launch_provider,launch_surface,launch_event_type,'
                    'source_observed_at,ingested_at,recorded_at FROM token_launch_facts '
                    'WHERE token_id=? ORDER BY source_observed_at,id LIMIT ?',
                    (token_id, row_limit+1))
                item['launch_history_truncated'] = len(launches) > row_limit
                item['creation_discovery'] = creation_discovery_timeline(
                    token, exposures[:row_limit], launches[:row_limit], snapshots,
                    cutoff.timestamp())
                first_exposure = item['creation_discovery']['first_exposure']
                first_quote = item['market_observations']['first_valid_recorded_pool_snapshot']
                exposure_time = stamp(first_exposure['recorded_at']) if first_exposure else None
                quote_time = stamp(first_quote['recorded_at']) if first_quote else None
                item['discovery_to_valid_pool_quote_seconds'] = (
                    quote_time - exposure_time if exposure_time is not None
                    and quote_time is not None and quote_time >= exposure_time else None)
                item['valid_pool_quote_preceded_discovery_exposure'] = bool(
                    exposure_time is not None and quote_time is not None
                    and quote_time < exposure_time)
                evaluations = []
                for start in range(0, len(snapshots), 400):
                    ids = [x['id'] for x in snapshots[start:start+400]]
                    placeholders = ','.join('?' for _ in ids)
                    evaluations += rows('SELECT id,source_snapshot_id,status,reason,evaluated_at '
                        'FROM chain_meme_trader_v6_entry_evaluations WHERE definition_version=? '
                        f'AND source_snapshot_id IN ({placeholders}) AND token_id=?', [version, *ids, token_id])
                evaluations = causal(evaluations, 'evaluated_at', 'evaluations')
                item['evaluation_sample_count'] = len(evaluations)
                item['evaluation_reasons'] = dict(Counter(x['reason'] for x in evaluations))
                item['first_evaluation'] = min(evaluations, key=lambda x: (stamp(x['evaluated_at']), x['id']), default=None)
                cohorts = rows('SELECT id,pair_address,entry_family,decided_at,source_snapshot_id '
                    'FROM chain_meme_trader_v6_cohorts WHERE definition_version=? AND token_id=? '
                    'ORDER BY decided_at,id LIMIT ?', (version, token_id, row_limit+1))
                item['cohort_history_truncated'] = len(cohorts) > row_limit
                cohorts = causal(cohorts[:row_limit], 'decided_at', 'cohorts')
                opportunities = []
                for cohort in cohorts:
                    decisions = rows('SELECT id,arm_id,status,reason,decided_at FROM '
                        'chain_meme_trader_entry_decisions WHERE definition_version=? AND shadow_cohort_id=?',
                        (version, cohort['id']))
                    decisions = causal(decisions, 'decided_at', f"decisions:{cohort['id']}")
                    fills = rows('SELECT id,execution_attempt_id,execution_result_id,filled_at,'
                        'entry_market_price_usd,execution_price_usd,output_token_quantity,slippage_bps FROM '
                        'chain_meme_trader_v6_entry_fills WHERE definition_version=? AND entry_cohort_id=?',
                        (version, cohort['id']))
                    fills = causal(fills, 'filled_at', f"fills:{cohort['id']}")
                    outcomes = rows('SELECT id,arm_id,entry_decision_id,entry_fill_id,outcome,'
                        'available_cash_usd,recorded_at FROM chain_meme_trader_entry_participant_outcomes '
                        'WHERE definition_version=? AND shadow_cohort_id=?', (version, cohort['id']))
                    outcomes = causal(outcomes, 'recorded_at', f"outcomes:{cohort['id']}")
                    opportunities.append(dict(cohort=cohort, arm_decisions=decisions,
                        source_fills=fills, participant_outcomes=outcomes))
                item['opportunities'] = opportunities
                item['admitted_arm_decisions'] = sum(x['status'] == 'admitted'
                    for o in opportunities for x in o['arm_decisions'])
                item['admitted_unique_cohorts'] = sum(any(x['status'] == 'admitted'
                    for x in o['arm_decisions']) for o in opportunities)
                positions = rows('SELECT arm_id,shadow_cohort_id,status,opened_at,closed_at,close_reason,'
                    'entry_snapshot_id,source_entry_fill_id,source_buy_trade_id,last_fill_id,'
                    'stake_usd,realized_pnl_usd,realized_proceeds_usd,allocated_cost_usd '
                    'FROM '
                    'chain_meme_trader_positions WHERE definition_version=? AND token_id=? '
                    'ORDER BY arm_id,shadow_cohort_id LIMIT ?', (version, token_id, row_limit+1))
                item['position_history_truncated'] = len(positions) > row_limit
                item['positions'] = causal(positions[:row_limit], 'opened_at', 'positions')
                item['first_position_at'] = min((x['opened_at'] for x in item['positions']), default=None)
                item['filled_unique_cohorts'] = len({x['shadow_cohort_id'] for x in item['positions']})
                safety = rows("SELECT id,pair_address,kind,recorded_at,"
                    "json_extract(payload_json,'$.cohort_id') cohort_id,"
                    "json_extract(payload_json,'$.snapshot_id') snapshot_id,"
                    "json_extract(payload_json,'$.requested_at') requested_at,"
                    "json_extract(payload_json,'$.expires_at') expires_at,"
                    "json_extract(payload_json,'$.assessment.reasons') reasons,"
                    "json_extract(payload_json,'$.assessment.unknowns') unknowns,"
                    "json_extract(payload_json,'$.safety_status') safety_status FROM chain_meme_pattern_evidence "
                    "WHERE definition_version=? AND token_id=? AND kind='preentry_obvious_scam_v1' "
                    "ORDER BY pair_address,kind,id DESC LIMIT ?", (version, token_id, row_limit+1))
                item['safety_history_truncated'] = len(safety) > row_limit
                item['safety_evidence'] = causal(safety[:row_limit], 'recorded_at', 'safety_evidence')
                for opportunity in opportunities:
                    opportunity['safety_evidence_ids'] = [x['id'] for x in item['safety_evidence']
                        if x['cohort_id'] == opportunity['cohort']['id']]
                if item['positions']:
                    item['path_status'] = 'paper_position_recorded_not_proof_of_early_capture'
                elif item['admitted_arm_decisions']:
                    item['path_status'] = 'admitted_without_position_requires_per_cohort_reason'
                elif evaluations:
                    item['path_status'] = 'evaluated_without_recorded_strategy_admission'
                elif snapshots:
                    item['path_status'] = 'snapshot_present_no_evaluation_in_sample'
                else:
                    item['path_status'] = 'discovered_no_snapshot'
            except sqlite3.OperationalError as exc:
                item['query_error'] = str(exc)
                item['path_status'] = 'incomplete_query_not_zero_activity'
        result['local_status'] = 'found' if matches else 'not_in_current_canonical_chain_ids'
        results.append(result)
        if time.monotonic() > deadline:
            break
    return dict(cutoff_utc=cutoff.isoformat(), finished_at=datetime.now(timezone.utc).isoformat(),
        definition_version=version, supplied_address_count=len(addresses), audited_address_count=len(results),
        remaining_addresses=addresses[len(results):], row_limit_per_history=row_limit, cases=results,
        scope='current_database_active_funding_period_ex_post_not_an_allowlist',
        limitations=['No Live quote/execution proof; no later price/ATH entry claims.',
            'Canonical supported chains only; legacy mixed-case/archived ledgers not searched.',
            'Cohorts are unique opportunity IDs, not statistically independent token samples.',
            'Invalid EVM lengths are retained with a warning, not silently discarded or repaired.',
            'Observation gaps use distinct same-pool times; cache freshness beyond stored fields unknown.',
            'Discovery exposure is one persisted source path, not proof of first-ever visibility; earlier market snapshots may precede it.',
            'Provider pair-created and launch-source event clocks become locally available only at their recorded/ingested times.',
            'A delayed first valid pool snapshot can reflect no tradable pool or delayed acquisition; this audit alone does not distinguish them.',
            'Evaluation coverage is bounded to sampled snapshot IDs; route tags are not risk rejections.'])


def markdown(report):
    lines = ['# 扩展用户地址诊断156', '', '仅当前数据库、当前资金期的只读证据；不是地址白名单或事后买入建议。',
        '', f"统计截止：{report['cutoff_utc']}；完整输出包含每个 cohort、策略决定及仓位主键。",
        '', '| 完整地址 / 链 | 快照样本 | 基础评估 | 准入机会 / 臂 | 已开仓机会 / 仓位 | 路径状态 |',
        '|---|---:|---:|---:|---:|---|']
    for case in report['cases']:
        if not case['matches']:
            lines.append(f"| `{case['address']}` | — | — | — | — | 当前规范化链标识未找到，非全历史未发现结论 |")
        for item in case['matches']:
            lines.append(f"| `{item['token']['token_id']}` | {item.get('sampled_snapshot_count','—')} | "
                f"{item.get('evaluation_sample_count','—')} | {item.get('admitted_unique_cohorts','—')} / "
                f"{item.get('admitted_arm_decisions','—')} | {item.get('filled_unique_cohorts','—')} / "
                f"{len(item.get('positions',[]))} | {item['path_status']} |")
    lines += ['', '## 创建与发现时点证据', '',
        '池创建及launch事件时间是供应商报告时间；只有对应本地观察/记录之后才可用，不能回填到事件时刻。'
        ' 首个本地发现标记缺失表示记录不完整或左截断，不等于系统当时绝对没有发现。', '',
        '| Token | 首次发现暴露 (观察 / 入库 / 来源) | 首个本地发现标记 | 最早已见池的报告创建 / 当时入库 | 首次有效候选池报告创建 / 报价入库 / 发现后秒数 | launch来源事件 / 入库 |',
        '|---|---|---|---|---|---|']
    for case in report['cases']:
        if not case['matches']:
            lines.append(f"| `{case['address']}` | 当前库无规范化身份 | — | — | — | — |")
        for item in case['matches']:
            timeline = item.get('creation_discovery') or {}
            exposure = timeline.get('first_exposure') or {}
            first_local = timeline.get('first_local_discovery_exposure') or {}
            pair = timeline.get('first_reported_pair_creation') or {}
            launch = timeline.get('first_launch_fact') or {}
            first_text = (f"{exposure.get('observed_at')} / {exposure.get('recorded_at')} / "
                f"{exposure.get('provider')}:{exposure.get('surface')}"
                if exposure else '未知')
            local_text = (f"{first_local.get('observed_at')} / {first_local.get('recorded_at')}"
                if first_local else '未知')
            pair_text = (f"{pair.get('reported_pair_created_at')} / "
                f"{pair.get('first_locally_recorded_at')}" if pair else '未知')
            quote = (item.get('market_observations') or {}).get('first_valid_recorded_pool_snapshot') or {}
            quote_delay = item.get('discovery_to_valid_pool_quote_seconds')
            quote_text = (f"{quote.get('reported_pair_created_at') or '未知'} / {quote.get('recorded_at')} / "
                f"{round(quote_delay, 3) if quote_delay is not None else '不可计算'}"
                if quote else '未知')
            launch_text = (f"{launch.get('source_observed_at')} / {launch.get('recorded_at')}"
                if launch else '未知')
            suffix = ' (历史截断)' if item.get('discovery_history_truncated') or item.get('launch_history_truncated') else ''
            lines.append(f"| `{item['token']['token_id']}` | {first_text} | {local_text} | "
                f"{pair_text} | {quote_text} | {launch_text}{suffix} |")
    lines += ['', '## 逐币首阻断与退出证据', '',
        '首评是该资金期首次被记录的判断，不代表此后始终被同一原因拒绝。'
        '安全状态是已记录的关联证据，不自动证明每个准入机会的最终失败原因。', '',
        '| 地址 / 链 | 本地首见 | 首评时间与原因 | 准入后执行或持仓 | 后续可证状态 |',
        '|---|---|---|---|---|']
    for case in report['cases']:
        if not case['matches']:
            lines.append(f"| `{case['address']}` | — | — | — | 当前库无规范化身份；不能推断历史不可发现 |")
            continue
        for item in case['matches']:
            first = item.get('first_evaluation') or {}
            first_text = (
                f"{first.get('evaluated_at', '—')} / `{first.get('reason', '—')}`"
                if first else '未在抽样帧内评估'
            )
            opportunities = item.get('opportunities') or []
            fills = sum(len(o.get('source_fills') or []) for o in opportunities)
            positions = item.get('positions') or []
            execution = (
                f"{item.get('admitted_unique_cohorts', 0)}准入机会 / "
                f"{fills}原始BUY成交 / {len(positions)}策略仓位"
            )
            if positions:
                closed = Counter(p.get('close_reason') or '未记录原因'
                    for p in positions if p.get('closed_at'))
                open_count = sum(not p.get('closed_at') for p in positions)
                reasons = ', '.join(f'{reason}:{count}' for reason, count in closed.most_common(3))
                later = f"首仓{item.get('first_position_at') or '—'}; 已平仓原因 {reasons or '—'}; 未平仓{open_count}"
            elif item.get('admitted_arm_decisions'):
                statuses = Counter(str(e.get('safety_status') or 'UNKNOWN')
                    for e in item.get('safety_evidence') or [])
                evidence = ', '.join(f'{status}:{count}' for status, count in statuses.most_common(3))
                later = f"已记安全状态 {evidence or '无'}; 无原始BUY成交" if not fills else '有原始BUY成交，未见策略仓位'
            else:
                reasons = Counter(item.get('evaluation_reasons') or {})
                later = '评估原因 ' + (', '.join(
                    f'{reason}:{count}' for reason, count in reasons.most_common(3)) or '无')
            if item.get('query_error') or any(item.get(key) for key in (
                'snapshot_history_truncated', 'cohort_history_truncated',
                'position_history_truncated', 'safety_history_truncated',
            )):
                later += '; 查询/历史抽样不完整'
            lines.append(f"| `{item['token']['token_id']}` | {item['token'].get('first_seen_at') or '—'} | "
                f"{first_text} | {execution} | {later.replace('|', '/')} |")
    lines += ['', '## 准入但未成交的逐机会记录', '',
        '安全记录仅按同一cohort关联；没有源BUY时不能把策略准入当作成交。', '',
        '| Token / cohort | 决策时点与原池 | 准入臂 | 关联安全状态 | 参与者终局 |',
        '|---|---|---:|---|---|']
    missing_fill_rows = 0
    for case in report['cases']:
        for item in case['matches']:
            for opportunity in item.get('opportunities') or []:
                admitted = sum(x.get('status') == 'admitted'
                    for x in opportunity.get('arm_decisions') or [])
                if not admitted or opportunity.get('source_fills'):
                    continue
                cohort = opportunity['cohort']
                linked = [e for e in item.get('safety_evidence') or []
                          if e.get('cohort_id') == cohort['id']]
                safety = ', '.join(f'{name}:{count}' for name, count in
                    Counter(str(e.get('safety_status') or 'UNKNOWN') for e in linked).most_common(4))
                outcomes = ', '.join(f'{name}:{count}' for name, count in
                    Counter(str(o.get('outcome') or 'UNKNOWN') for o in
                            opportunity.get('participant_outcomes') or []).most_common(4))
                lines.append(f"| `{item['token']['token_id']}` / {cohort['id']} | "
                    f"{cohort.get('decided_at') or '—'} / `{cohort.get('pair_address') or '—'}` | "
                    f"{admitted} | {safety or '无关联记录'} | {outcomes or '无终局回执'} |")
                missing_fill_rows += 1
    if not missing_fill_rows:
        lines.append('| — | — | — | 当前抽样内无此类机会 | — |')
    lines += ['', '## 已买入策略仓的逐仓结果', '',
        '已实现PnL只表示账本已实现部分；开放仓不在此处按后来行情估值。'
        '重复策略仓不等于独立源BUY或独立Token。', '',
        '| Token / 策略 / cohort | 原池 / 源BUY | 开仓 / 平仓 | 状态与退出原因 | 投入U / 已实现PnL U / 末次fill |',
        '|---|---|---|---|---|']
    position_rows = 0
    for case in report['cases']:
        for item in case['matches']:
            pools = {o['cohort']['id']: o['cohort'].get('pair_address')
                     for o in item.get('opportunities') or []}
            for position in item.get('positions') or []:
                cohort_id = position['shadow_cohort_id']
                lines.append(f"| `{item['token']['token_id']}` / `{position['arm_id']}` / {cohort_id} | "
                    f"`{pools.get(cohort_id) or 'UNKNOWN'}` / {position.get('source_entry_fill_id') or '—'} | "
                    f"{position.get('opened_at') or '—'} / {position.get('closed_at') or '—'} | "
                    f"{position.get('status') or '—'}; {position.get('close_reason') or '—'} | "
                    f"{position.get('stake_usd') if position.get('stake_usd') is not None else '—'} / "
                    f"{position.get('realized_pnl_usd') if position.get('realized_pnl_usd') is not None else '—'} / "
                    f"{position.get('last_fill_id') or '—'} |")
                position_rows += 1
    if not position_rows:
        lines.append('| — | — | — | 当前抽样内无仓位 | — |')
    lines += ['', '## 边界', '', *('- '+x for x in report['limitations']),
              f"- 未处理地址：{len(report['remaining_addresses'])}；query_error 或 history_truncated 不得解读为完整统计。"]
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--addresses-file', type=Path)
    parser.add_argument('--report-json', type=Path,
        help='Re-render an existing frozen audit without querying the live database')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--seconds', type=float, default=30)
    args = parser.parse_args()
    if args.report_json:
        report = json.loads(args.report_json.read_text(encoding='utf-8'))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        target = args.output_dir / (args.report_json.stem + '_attribution.md')
        target.write_text(markdown(report), encoding='utf-8')
        print(json.dumps(dict(addresses=report['supplied_address_count'],
            completed=report['audited_address_count'], output=str(target))))
        raise SystemExit(0)
    if args.addresses_file is None:
        parser.error('--addresses-file is required unless --report-json is given')
    text = args.addresses_file.read_text(encoding='utf-8-sig')
    addresses = addresses_from_text(text)
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    database = (ROOT / config['database']).resolve()
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True, timeout=.2) as con:
        con.row_factory = sqlite3.Row
        con.execute('BEGIN')  # one bounded read snapshot, not mixed live frontiers
        version = json.loads(con.execute("SELECT value_json FROM kv WHERE key='runtime-loaded-manifest'").fetchone()[0])['definition_version']
        report = audit(con, addresses, version, seconds=args.seconds)
    report['objective_sha256'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (args.output_dir / f'cases_{suffix}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output_dir / f'cases_{suffix}.md').write_text(markdown(report), encoding='utf-8')
    print(json.dumps(dict(addresses=len(addresses), completed=report['audited_address_count'],
        matched=sum(bool(x['matches']) for x in report['cases']), output=str(args.output_dir / f'cases_{suffix}.md'))))
