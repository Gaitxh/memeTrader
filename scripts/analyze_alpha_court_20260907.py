"""Read-only court recommendations; never updates runtime strategy state."""
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/research/alpha_diagnosis_20260907'
DOC = ROOT / 'docs/PROJECT_CONTEXT/ALPHA_DIAGNOSIS_20260907'
B = json.loads((DATA / 'BOUNDARY.json').read_text())
REPAIR = '2026-09-07T09:19:47Z'


def main():
    rows = list(csv.DictReader((DOC / 'STRATEGY_BEHAVIOR_FAMILIES.csv').open(encoding='utf-8-sig')))
    con = sqlite3.connect('file:' + Path(B['database']).as_posix() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    paths = defaultdict(lambda: defaultdict(list))
    totals = defaultdict(lambda: defaultdict(float))
    # Append-only trades establish as-of economics, independent of later position mutations.
    last = 0
    while True:
        batch = con.execute('''SELECT id,arm_id,token_id,shadow_cohort_id,side,gross_usd,
            net_cash_flow_usd,realized_pnl_usd,created_at,reason FROM chain_meme_trader_trades
            WHERE definition_version=? AND id>? AND id<=? AND created_at<=?
            ORDER BY id LIMIT 2000''', (B['version'], last, B['frontiers']['chain_meme_trader_trades'], B['cutoff_utc'])).fetchall()
        if not batch:
            break
        for r in batch:
            key = (r['token_id'], r['shadow_cohort_id'])
            paths[r['arm_id']][key].append(tuple(r[k] for k in ('side','gross_usd','net_cash_flow_usd','created_at','reason')))
            totals[r['arm_id']][r['token_id']] += float(r['realized_pnl_usd'] or 0)
        last = batch[-1]['id']
    con.close()
    groups = defaultdict(list)
    for r in rows:
        groups[r['economic_fingerprint']].append(r)
    comparisons, court, family_court = [], [], []
    promising = {'finalist_progress_clock_v1', 'round2_giveback_duration_candidate_v1'}
    low_information = {'finalist_depth_divergence_v1','finalist_activity_failure_v1',
                       'round2_slow_grace_candidate_v1','round2_response_exhaustion_candidate_v1',
                       'round2_runner_requalification_candidate_v1','resource_profit_structure_candidate_v1'}
    for family, members in sorted(groups.items()):
        members.sort(key=lambda r: (r['activated_at'], r['arm_id']))
        representative = members[0]['arm_id']
        for r in members:
            arm = r['arm_id']
            own = paths[arm]
            common = set(own) & set(paths[representative])
            shared_tokens = len({t for t, _ in common})
            same = sum(own[k] == paths[representative][k] for k in common)
            # Empty histories cannot establish equality; timing/reasons are included in paths.
            observed_identical = arm != representative and len(common) > 0 and same == len(common)
            same_declared = r['contract_hash'] == members[0]['contract_hash']
            if int(r['contaminations']):
                state, reason = 'ENGINEERING_CONTAMINATED', 'recorded contamination requires era-specific adjudication'
            elif observed_identical and same_declared:
                state, reason = 'RETIRE_DUPLICATE', 'same contract and identical common trade paths; preserve representative/history'
            elif arm in promising:
                state, reason = 'PROMISING_UNPROVEN', 'positive matched exit delta, token interval crosses zero'
            elif arm in low_information:
                state, reason = 'FREEZE_NEW_ENTRY', 'current matched terminal paths add zero or negligible economic distinction; recommendation only'
            elif r['status'] == 'dormant_coverage_unknown':
                state, reason = 'KEEP_INFORMATIONAL', 'coverage unknown; do not equate no BUY with missing input or no trigger; no expansion'
            elif 'control' in arm or arm == 'finalist_baseline_v1' or (len(members) > 1 and arm == representative):
                state, reason = 'KEEP_BENCHMARK', 'reference for common opportunity/exit comparisons; not alpha endorsement'
            else:
                state, reason = 'KEEP_INFORMATIONAL', 'distinct mapped contract; economic edge not established; research queue only'
            result = dict(arm_id=arm,economic_family=family,representative=representative,
                          recommendation=state,reason=reason,common_opportunities=len(common),
                          common_tokens=shared_tokens,identical_full_trade_paths=same,
                          own_only_opportunities=len(set(own)-set(paths[representative])),
                          representative_only_opportunities=len(set(paths[representative])-set(own)))
            court.append(result)
            if arm != representative:
                comparisons.append(result)
        entries = [x for x in court if x['economic_family'] == family]
        states = dict(Counter(x['recommendation'] for x in entries))
        family_court.append(dict(family=family,representative=representative,arms=len(members),states=states))
    out = DATA / 'court'
    out.mkdir(exist_ok=True)
    for name, data in [('arm_court.csv',court),('duplicate_comparisons.csv',comparisons)]:
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            w = csv.DictWriter(f,fieldnames=list(data[0])); w.writeheader(); w.writerows(data)
    counts = dict(Counter(r['recommendation'] for r in court))
    (out/'summary.json').write_text(json.dumps({'cutoff':B['cutoff_utc'],'counts':counts,'families':family_court},indent=2),encoding='utf-8')
    lines = ['# Strategy Court — 仅建议，未修改运行状态', '',
      '判决依据是当前合同、冻结前沿的追加交易路径及共同入场退出证据。KEEP 是研究角色，不是所有账户无限运行的建议。152 是字段/dispatch 归类数，不能断言152个独立经济思想；实际发生差异的机制更少。', '',
      'RETIRE_DUPLICATE 要求同声明合同、非空共同机会的完整交易路径一致（包括时间、金额、原因）；异步激活/现金约束导致的非共同机会另计。它不保证未来所有路径一致。FREEZE_NEW_ENTRY 只针对当前低信息退出实验，已有仓位应按原合同退出；本轮没有执行这些生产操作。', '',
      '无BUY的14臂仍为覆盖未明，不能无证据判 INPUT_NOT_AVAILABLE；该状态不应成为永久保留理由。下一轮先解释输入/触发/容量分母。没有凭零污染行认定所有历史工程正确。', '',
      '账户建议计数：`' + json.dumps(counts,ensure_ascii=False) + '`。详细可重算证据：`data/research/alpha_diagnosis_20260907/court/arm_court.csv`。', '',
      '## 全部行为家族', '', '| Family | 参考 arm | 账户数 | 家族内建议 |','|---|---|---:|---|']
    for r in family_court:
        lines.append(f"| {r['family']} | {r['representative']} | {r['arms']} | {json.dumps(r['states'])} |")
    lines += ['', '## 全部账户裁决', '', '| Arm | 建议 | 共同机会 / Token | 相同完整路径 |','|---|---|---:|---:|']
    for r in court:
        lines.append(f"| {r['arm_id']} | {r['recommendation']} | {r['common_opportunities']} / {r['common_tokens']} | {r['identical_full_trade_paths']} |")
    (DOC/'STRATEGY_COURT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
