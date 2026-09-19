"""Manual review of frozen policy/position files; never edits runtime or trades.
Rule descriptors and code references are navigation, not proof of equivalence.
All common outcomes including losses and ties remain in the research denominator.
"""
from __future__ import annotations
import argparse, ast, collections, datetime, hashlib, json, math, pathlib, statistics
ROOT = pathlib.Path(__file__).resolve().parents[1]
TERMINAL = {'closed', 'written_off'}

def stats(rows):
    good=[]; invalid=0
    for row in rows:
        if row.get('status') not in TERMINAL: continue
        try:
            stake=float(row['stake_usd']); pnl=float(row['realized_pnl_usd'])
            if not math.isfinite(stake) or stake<=0 or not math.isfinite(pnl): raise ValueError()
        except (KeyError, TypeError, ValueError): invalid+=1; continue
        good.append(row)
    values=[float(r['realized_pnl_usd']) for r in good]
    tokens=collections.defaultdict(float)
    for row in good: tokens[row['token_id']]+=float(row['realized_pnl_usd'])
    gain=math.fsum(v for v in values if v>0); loss=-math.fsum(v for v in values if v<0)
    net=math.fsum(values); count=len(good)
    writeoffs=[r for r in good if r['status']=='written_off']
    return dict(positions=len(rows),terminal_positions=count,terminal_tokens=len(tokens),
        open_positions=sum(r.get('status')=='open' for r in rows),invalid_terminals=invalid,
        net_usd=net,mean_position_pnl=net/count if count else None,
        median_position_pnl=statistics.median(values) if count else None,
        winning_positions=sum(v>0 for v in values),losing_positions=sum(v<0 for v in values),
        profit_factor=gain/loss if loss else None,profit_factor_undefined=not bool(loss),
        written_off_positions=len(writeoffs),
        full_loss_writeoffs=sum(isinstance(r.get('realized_proceeds_usd'),(int,float)) and not isinstance(r['realized_proceeds_usd'],bool) and math.isfinite(r['realized_proceeds_usd']) and 0<=r['realized_proceeds_usd']<=1e-9 for r in writeoffs),
        positive_pnl_writeoffs=sum(float(r['realized_pnl_usd'])>0 for r in writeoffs),
        median_token_pnl=statistics.median(tokens.values()) if tokens else None,
        top_token_pnl=max(tokens.values()) if tokens else None,
        net_without_best_token=net-max(tokens.values()) if len(tokens)>1 else None,
        net_without_worst_token=net-min(tokens.values()) if len(tokens)>1 else None)

def disposition(policy, result, chains):
    if policy.get('entry_paused'): return 'PRESERVE_EXISTING_PAUSE_AND_EXITS'
    if result['invalid_terminals']: return 'REVIEW_INVALID_MONEY_NOT_RANKABLE'
    if not result['terminal_positions']: return 'FORWARD_PENDING_NO_TERMINAL_EVIDENCE'
    if result['terminal_tokens']<30: return 'FORWARD_SAMPLE_INSUFFICIENT'
    if result['net_usd']<0 and any(c['net_usd']>0 for c in chains.values()):
        return 'MIXED_CHAIN_EVIDENCE_NO_BLANKET_CONCLUSION'
    if result['net_usd']<0: return 'NEGATIVE_OBSERVED_REVIEW_MECHANISM_AND_CONTROL'
    if result['net_without_best_token'] is not None and result['net_without_best_token']<=0:
        return 'POSITIVE_TAIL_DEPENDENT_UNPROVEN'
    return 'POSITIVE_OBSERVED_NOT_PROVEN_EXPECTANCY'

def code_index(root):
    index=collections.defaultdict(list)
    for path in sorted((root/'src/memetrader').glob('*.py')):
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                if '\n' not in node.value and len(node.value)<180:
                    index[node.value].append(f'{path.relative_to(root).as_posix()}:{node.lineno}')
    return index

def entry_availability(policies):
    """Static upper bound only; no claim about signal, cash, market or fill eligibility."""
    groups=collections.defaultdict(list)
    for p in policies:
        if p.get('entry_paused') or not p.get('forward_enabled',True): continue
        if p.get('paired_entry_group'):
            groups[(p.get('entry_match_mode'),p['paired_entry_group'])].append(p)
    result={}
    for p in policies:
        arm=p['arm_id']
        if p.get('entry_paused'): state='PAUSED'
        elif not p.get('forward_enabled',True): state='FORWARD_DISABLED'
        elif p.get('paired_entry_group'):
            members=groups[(p.get('entry_match_mode'),p['paired_entry_group'])]
            try:
                expected={int(x.get('paired_entry_size',2)) for x in members}
                state=('ELIGIBLE_SUBJECT_TO_RUNTIME_CHECKS' if expected=={len(members)}
                       else 'PAIRED_DEPENDENCY_INCOMPLETE')
            except (ValueError,TypeError,OverflowError): state='PAIR_CONTRACT_UNKNOWN'
        else: state='ELIGIBLE_SUBJECT_TO_RUNTIME_CHECKS'
        result[arm]={'state':state,'paired_entry_group':p.get('paired_entry_group'),
                     'required_pair_size':p.get('paired_entry_size')}
    return result


def inactivity(policy, rows, *, as_of, availability, by_policy):
    """Frozen-cutoff diagnosis, not a live entry gate or automatic parameter update."""
    result = dict(as_of=as_of,last_entry_at=None,hours_without_entry=None,
        state='CUTOFF_UNKNOWN',review_required=False,entry_attempts='not_measured')
    if not as_of:
        return result
    def clock(value):
        parsed = datetime.datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('explicit timezone required')
        return parsed
    try:
        end=clock(as_of); start=clock(policy['forward_started_at'])
        entries=[clock(r['opened_at']) for r in rows]
    except (KeyError,TypeError,ValueError):
        result['state']='CLOCK_UNKNOWN'
        return result
    if start>end:
        result['state']='NOT_ACTIVATED_AT_CUTOFF'
        return result
    visible=[x for x in entries if start<=x<=end]
    last=max(visible,default=None)
    result.update(last_entry_at=last.isoformat() if last else None,
        hours_without_entry=(end-(last or start)).total_seconds()/3600,
        entries_at_cutoff=len(visible),future_rows_excluded=sum(x>end for x in entries))
    if policy.get('entry_paused'):
        result['state']='EXPECTED_PAUSE'
        return result
    structural=availability.get('state','UNKNOWN')
    if structural!='ELIGIBLE_SUBJECT_TO_RUNTIME_CHECKS':
        result.update(state=structural,review_required=structural!='FORWARD_DISABLED')
        return result
    if policy.get('entry_filter',{}).get('failed_impulse_cooling'):
        core=by_policy.get('resource_age_rate_candidate_v1')
        if core is None or core.get('entry_paused') or not core.get('forward_enabled',True):
            result.update(state='NEW_TOKEN_PARENT_TRADE_UNAVAILABLE',review_required=True,
                prerequisite='resource_age_rate_candidate_v1',
                caveat='Older same-pool loss receipts may qualify; no new parent trades can be generated.',
                next_action='Revise to independent observable recovery; do not reactivate failed parent.')
            return result
    if result['hours_without_entry']>=24:
        result.update(state='NEVER_ENTERED_24H' if last is None else 'NO_NEW_ENTRY_24H',
            review_required=True,next_action='Inspect actual input, signal and rejection evidence; absence is not market-no-opportunity proof.')
    else:
        result['state']='NO_ENTRY_YET_UNDER_24H' if last is None else 'RECENT_ENTRY'
    return result


def review(definition, positions, root=ROOT, *, as_of=None):
    from memetrader.alpha149 import SPECS, EXIT_ARMS
    by_arm=collections.defaultdict(list)
    for row in positions: by_arm[row['arm_id']].append(row)
    availability=entry_availability(definition['policies'])
    by_policy={p['arm_id']:p for p in definition['policies']}
    index=code_index(root); result=[]; fingerprints=collections.defaultdict(list)
    for policy in definition['policies']:
        arm=policy['arm_id']; rows=by_arm[arm]; overall=stats(rows)
        chain_rows=collections.defaultdict(list)
        for row in rows: chain_rows[row['token_id'].split(':',1)[0]].append(row)
        chains={chain:stats(items) for chain,items in chain_rows.items()}
        contract=(policy.get('entry_filter') or {}).get('contract')
        feature=policy.get('feature_contract')
        descriptor={'entry_mode':policy.get('entry_match_mode'),'feature_contract':feature,
            'entry_contract':contract,'entry_family':policy.get('entry_family'),
            'entry_alias_of':policy.get('entry_alias_of'),'source_arms':policy.get('source_arm_ids'),
            'alpha149_kind':SPECS[arm][0] if arm in SPECS else None,
            'shared_exit_carrier':arm in EXIT_ARMS,
            'filters':policy.get('entry_filter'),
            'exits':{k:v for k,v in policy.items() if any(w in k for w in ('exit','stop','hold','profit','trailing'))}}
        references=sorted(set(index.get(arm,[])+index.get(feature,[])+index.get(contract,[])))
        signature=policy.get('behavior_contract_hash')
        if signature: fingerprints[signature].append(arm)
        result.append(dict(arm_id=arm,name=policy.get('name'),entry_paused=bool(policy.get('entry_paused')),
            lifecycle=policy.get('account_lifecycle'),assessment=policy.get('assessment_status'),
            pause_reason=policy.get('entry_pause_reason') or policy.get('assessment_note'),
            activated_at=policy.get('forward_started_at'),frontier=policy.get('forward_activation_snapshot_id'),
            behavior_contract_hash=signature,rule_descriptor=descriptor,source_references=references,
            entry_availability=availability[arm],
            inactivity=inactivity(policy,rows,as_of=as_of,availability=availability[arm],by_policy=by_policy),
            metrics=overall,chains=chains,disposition=disposition(policy,overall,chains)))
    return dict(generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        position_cutoff=as_of,
        inactivity_counts=dict(collections.Counter(r['inactivity']['state'] for r in result)),
        policies=len(result),dispositions=dict(collections.Counter(r['disposition'] for r in result)),
        entry_capable=sum(not r['entry_paused'] for r in result),
        entry_capable_definition='legacy unpaused count; not actual admissibility',
        structural_entry_upper_bound=sum(v['state']=='ELIGIBLE_SUBJECT_TO_RUNTIME_CHECKS' for v in availability.values()),
        entry_availability_counts=dict(collections.Counter(v['state'] for v in availability.values())),
        hash_groups=[dict(hash=k,arms=v) for k,v in fingerprints.items() if len(v)>1],
        missing_literal_code_reference=[r['arm_id'] for r in result if not r['source_references']],
        rows=result,scope='Frozen files, all effective policies; raw account outcomes, not an additive portfolio.',
        caveats=['Rule descriptors and equal hashes do not prove equivalent behavior across code versions.',
                 'A chain split or positive tail is descriptive discovery evidence, not validated alpha.',
                 'No policy control, order, position or configuration is changed by this report.',
                 'No terminal-only PnL curve is mislabeled as full-equity maximum drawdown.'])

def markdown(report):
    lines=['# 全策略逐账户复核233','',report['scope'],'',
        '| 策略 | 新开仓 | 终局仓位 / Token | 净PnL U | 核销 / 全损 | 去掉最好Token后U | 处置 |',
        '|---|---|---:|---:|---:|---:|---|']
    for row in report['rows']:
        m=row['metrics']; drop=m['net_without_best_token']
        lines.append(f"| `{row['arm_id']}` | {row.get('entry_availability',{}).get('state', 'UNKNOWN')} | "
            f"{m['terminal_positions']} / {m['terminal_tokens']} | {m['net_usd']:.4f} | "
            f"{m['written_off_positions']} / {m['full_loss_writeoffs']} | "
            f"{f'{drop:.4f}' if drop is not None else 'NA'} | {row['disposition']} |")
    lines+=['','完整规则、分链指标、源码定位和激活前沿见同名JSON。处置为本次复核分类，不是自动控制。',
            '',*report['caveats']]
    lines += ['', '## 无交易及依赖复核', '', '统计截止：'+str(report.get('position_cutoff') or '未提供；不推断停滞时长'), '', '| 策略 | 最后入场 | 小时 | 诊断 |', '|---|---|---:|---|']
    for row in report['rows']:
        d=row.get('inactivity',{})
        if d.get('review_required'):
            hours=d.get('hours_without_entry')
            lines.append('| '+row['arm_id']+' | '+str(d.get('last_entry_at') or '从未入场')+' | '+(str(round(hours,2)) if hours is not None else 'NA')+' | '+d['state']+' |')
    return '\n'.join(lines)+'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policies',type=pathlib.Path,required=True)
    parser.add_argument('--positions',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    definition=json.loads(args.policies.read_text(encoding='utf-8-sig'))
    positions=json.loads(args.positions.read_text(encoding='utf-8-sig'))
    result=review(definition,positions['rows'],as_of=positions.get('as_of'))
    result['position_cutoff']=positions.get('as_of')
    result['inputs_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (args.policies,args.positions)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    args.output.with_suffix('.md').write_text(markdown(result),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('policies','dispositions','entry_capable')},ensure_ascii=False))

if __name__=='__main__': main()
