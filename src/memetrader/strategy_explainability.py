"""Deterministic display projection of effective/frozen contracts; no database access."""
import json

ASSESSMENTS = ('ACTIVE','FAILED','EXPERIMENT_COMPLETE_POSITIVE','DUPLICATE_SUPERSEDED','DATA_BLOCKED','INSUFFICIENT','ENGINEERING_CONTAMINATED')
LABELS = {'ACTIVE':'正在前向验证；运行状态不代表已证实盈利。','FAILED':'已有评估记录将该实验归为失败；范围以证据记录为准。','EXPERIMENT_COMPLETE_POSITIVE':'正收益实验已完成，不是失败；暂停新增资本与历史盈利并不矛盾。','DUPLICATE_SUPERSEDED':'重复行为或已被代表策略替代；保留历史和对照价值。','DATA_BLOCKED':'当前数据输入不足以支持原规则，不通过放宽规则制造样本。','INSUFFICIENT':'尚无足够评估证据；不能据暂停状态推断失败。'}
LABELS['ENGINEERING_CONTAMINATED']='已标记工程污染；保留账本并单独解释受影响样本，不将其直接判为策略失败。'
PARAMS = {'min_age_seconds':'池龄至少（秒）','max_age_seconds':'池龄最多（秒）','min_liquidity_usd':'流动性至少（美元）','max_liquidity_usd':'流动性最多（美元）','min_rate_acceleration':'活动速率加速度至少','cooling_retrace_fraction':'冷却回撤比例','max_gap_seconds':'有效观察最大间隔（秒）','min_volume_5m_usd':'5分钟成交额至少（美元）','min_buys_5m':'5分钟买入笔数至少','min_buy_share':'买入笔数占比至少','max_concurrent_positions':'同时持仓上限','minimum_candidates':'候选数量下限','direction':'条件分支','control':'是否对照分支','opportunity':'机会/入场次数约束','occupied_signal_policy':'已有仓位时的信号处理','contract':'冻结规则版本'}
VALUES = {'age_rate':'按池龄归一化活动速率','reject_without_queue_or_replay':'拒绝当前信号，不排队或历史重放','first_common_eligible_frame_per_pool':'每池首次共同满足条件的观察','next_observation':'下一有效观察'}

def value(v):
    if v is True:return '是'
    if v is False:return '否'
    if v is None:return 'UNKNOWN（未配置/未提供）'
    if isinstance(v,str):return VALUES.get(v,v)
    return json.dumps(v,ensure_ascii=False,sort_keys=True)

def pct(v):
    try:return f'{float(v)*100:g}%'
    except (ValueError,TypeError):return value(v)

def strategy_logic(policy, family, control=None, *, current=False):
    p=policy or {};c=control or {};f=p.get('entry_filter') or {}
    operation=p.get('account_lifecycle') or family.get('account_lifecycle') or ('ACTIVE_FORWARD' if current and p.get('forward_enabled',True) else 'FROZEN_HISTORY')
    assessment=p.get('assessment_status') or family.get('assessment_status') or c.get('assessment_status')
    if assessment not in ASSESSMENTS:assessment='ACTIVE' if operation=='ACTIVE_FORWARD' else 'INSUFFICIENT'
    note=p.get('assessment_note') or c.get('assessment_note') or family.get('assessment_note') or 'UNKNOWN：未提供独立评估说明。'
    pause=c.get('reason') or p.get('entry_pause_reason') or p.get('stop_reason') or family.get('stop_reason') or 'UNKNOWN：未提供原始暂停依据。'
    evidence=p.get('assessment_evidence') or c.get('assessment_evidence') or family.get('assessment_evidence') or 'UNKNOWN：未提供评估工件。'
    entry=[f"入场机制：{value(p.get('entry_family') or family.get('entry_family'))}"]
    if p.get('feature_contract')=='dex-trajectory/v1':
        rules=p.get('trajectory_rules') or {}
        entry.extend([rules.get('common','UNKNOWN'),rules.get(p.get('feature_hypothesis'),'UNKNOWN')])
    if p.get('trajectory_engine')=='v144':
        rules=p.get('entry_rules144') or {}
        rule=rules.get(p.get('arm_id')) if isinstance(rules,dict) else rules
        entry.append('v144 冻结入场规则：'+(str(rule) if rule else 'UNKNOWN'))
        if p.get('entry_alias_of'):
            entry.append('来源同一冻结信号：'+str(p['entry_alias_of'])+'；新账户只从自身激活后的同源信号前向开始。')
    if p.get('router_priority'):
        entry.append('冻结优先级（一次只选一支）：'+' → '.join(p['router_priority']))
        entry.append('完整复用所选来源的信号、激活时点和原池后帧；未选择/缺失分支原因随决定保存。造势分支由独立1U执行器处理；分发/不可卖只作风险，不买入。')
    entry += [f'{PARAMS.get(k,"冻结条件 "+k)}：{value(v)}' for k,v in f.items()]
    for k,label in [('entry_gate','候选准入通道'),('entry_match_mode','信号匹配方式'),('source_entry_family','复用的入场机制')]:
        if k in p:entry.append(f'{label}：{value(p[k])}')
    if not p:entry.append('UNKNOWN：本历史版本未提供 frozen_policy，不能从当前策略反推旧规则。')
    sequence=['候选进入该策略的数据/准入通道','只按该版本配置判断信号']
    sequence.append('信号后严格较晚的有效观察，才可继续执行；信号价不是成交价' if p.get('require_post_decision_observation') or p.get('requires_distinct_trajectory_frame') else '后帧要求：UNKNOWN（本配置未明确后帧合同）')
    if p.get('requires_distinct_trajectory_frame'):
        sequence.append('v144 还要求独立轨迹后帧及实际窗口；缓存时间不能伪装成新行情。')
    sequence.append('最终 BUY 共用安全门：拒绝或等待不能当作通过；这是当前执行约束，不补写历史' if current else '历史安全/成交约束只以该版本冻结合同为准，不能套用今日规则')
    sequence.append('Paper 按成交时有效成本模型和可用资金结算；展示信号不代表已 BUY')
    if p.get('native_execution'):
        sequence=['官方 Pump 曲线身份和支持的 SOL 状态通过，至少两个独立帧形成吸收信号',
            '下一独立曲线帧重新报价，并核验当前 Token 控制、买入后即时卖回与现金预算',
            '同一封存收据绑定买卖消息费用和账户租金；租金、手续费、卖出费预留单列',
            '按后帧协议模型写入 Paper 现金与仓位；没有链上广播或真实交易']
    exits=[]
    if p.get('trajectory_exit'):
        exits.append({'velocity':'买后30秒价格速度与加速度转负、滚动活动与流动性同时下降时申请退出。',
            'liquidity_divergence':'买后30秒价格仍上涨、流动性下降超过双边摩擦尺度时申请退出。',
            'blowoff':'买后30秒价格大幅上涨但减速、成交额和笔数仍扩大时申请退出。'}.get(p['trajectory_exit'],'UNKNOWN'))
        exits.append('只使用新鲜买后原池观察；机械止损/追踪/最大持有仍保留；后续有效行情才结算。')
    if p.get('trajectory_trend_runner') or p.get('trajectory145_trend_evidence'):
        exits.append('趋势续持：先按 30 分钟基础期限管理；仅新的 300 秒实际趋势、活动和流动性健康证据可续至绝对 120 分钟。硬止损、死面和结构失效优先。')
    for k,label in [('hard_stop_return','硬止损收益阈值（计价口径见退出合同）'),('trailing_activate_return','追踪退出激活收益阈值'),('trailing_drawdown','激活后追踪回撤阈值')]:
        if k in p:exits.append(f'{label}：{pct(p[k])}')
    if 'max_hold_minutes' in p:exits.append(f"普通最长持仓：{value(p['max_hold_minutes'])} 分钟（特殊 overlay 另列）")
    if 'take_profit' in p:
        if not p['take_profit']:exits.append('固定分批止盈：未配置')
        else:
            for i,tier in enumerate(p['take_profit'],1):
                if isinstance(tier,dict) and 'return' in tier and 'fraction_of_remaining' in tier:
                    exits.append(f"第{i}档止盈：收益达到 {pct(tier['return'])} 时申请卖出剩余仓位的 {pct(tier['fraction_of_remaining'])}；触发不等于已成交。")
                else:exits.append(f'第{i}档冻结止盈配置：{value(tier)}')
    dynamic=p.get('dynamic_principal_recovery')
    if dynamic:
        exits.append('动态本金回收：按实际净卖出模型求可回收原始支出的最小卖出量，后帧重新计算；只有实际结算回款才算回本。')
        if 'keep_half' in str(dynamic):exits.append('仅当所需卖出量不超过剩余数量的一半时回收；否则继续父策略普通退出。')
        exits.append('动态回收合同：'+str(dynamic))
    if p.get('runner_max_hold_minutes_after_recovery'):
        exits.append('只有真实部分卖出后账本确认累计净回款覆盖原始支出且仍有余仓，最长持仓才变为'+str(p['runner_max_hold_minutes_after_recovery'])+'分钟；未成交的回本申请不生效，不由Agent延长。')
    if f.get('narrative_hold_v2'):exits.append('叙事 overlay：只允许实际回本后的健康剩余仓，经持久化独立扩张证据延长软持仓；不覆盖硬止损/核销。未核验则普通退出。')
    for k,v in p.items():
        if k not in {'exit_family','exit_mode','hard_stop_return','trailing_activate_return','trailing_drawdown','max_hold_minutes','take_profit','dynamic_principal_recovery'} and any(x in k for x in ('exit','hold','partial','stop','overlay')):
            exits.append(f'特殊退出配置 {k}：{value(v)}')
    if p.get('native_execution'):
        exits.extend(['原生剩余数量使用当前曲线卖回报价；净价值低于原始支出80%触发硬止损，达到130%后回撤15%触发追踪退出。',
            '300秒到期先保存退出意图，下一独立有效状态才可成交；储备不足或报价缺失保留 UNKNOWN，不伪造卖出。',
            '已触发退出时，可按当前真实容量部分卖回；逐笔扣除已消耗的 Paper 储备额度并按实际数量核算费用，剩余仓继续等待，不能重复使用同一份流动性。',
            '曲线毕业后只接经过验证的规范 PumpSwap 后继池；等待身份/报价期间不在旧曲线上成交。'])
    else:exits.append('退出机制/模式：'+value(p.get('exit_family') or family.get('exit_family'))+' / '+value(p.get('exit_mode')))
    requirements=['必须有策略配置要求的身份绑定、时间有效性和特征；缺失值不是零，也不是条件已满足。']
    if p.get('trajectory_engine')=='v144':
        for key,item in (p.get('data_contract') or {}).items():
            requirements.append('v144 数据合同 '+str(key)+'：'+value(item))
        if p.get('model_contract'):
            requirements.append('模式选择合同：'+str(p['model_contract'])+'；冷启动为固定基线，未发布模型不改变新订单。')
    if current:requirements.append('原生曲线按协议储备、Token 控制、费用与卖回容量验证；不套用毕业前 DEX 流动性底线。' if p.get('native_execution') else '当前 Paper 原池价格/流动性及严格时序有效；明确低于执行流动性底线按现有退出规则处理。')
    execution=p.get('_execution') or {}
    requirements += [f'成交配置 {k}：{value(v)}' for k,v in execution.items()]
    risks=[f"单笔名义金额（美元）：{value(p.get('notional_usd'))}",f"同时持仓上限：{value(f.get('max_concurrent_positions'))}",'样本、PF、期望和回撤为事实指标；正收益或绿色不等于 Alpha，同币/同成交账户不是独立样本。']
    return dict(purpose=p.get('description') or family.get('description') or 'UNKNOWN：未提供策略目的。',entry_rules=entry,entry_sequence=sequence,exit_rules=exits,data_requirements=requirements,risk_controls=risks,
        lineage=dict(source_arm_ids=p.get('source_arm_ids') or [],revision=p.get('strategy_revision') or family.get('strategy_revision'),paired_entry_group=p.get('paired_entry_group'),paired_entry_size=p.get('paired_entry_size'),policy_source='effective_policy' if current else 'frozen_policy' if p else 'UNKNOWN'),
        lifecycle_explanation=dict(assessment=assessment,operation=operation,note=LABELS[assessment]+' '+str(note),evidence=evidence,pause_basis=pause if operation!='ACTIVE_FORWARD' else '仍按当前有效配置参加前向；不自动代表已验证有效。',lesson=p.get('failure_lesson') or c.get('lesson') or '仅以以上评估记录为依据；未记录独立因果教训，不自动推断。',benchmark=p.get('benchmark_note') or c.get('benchmark_note') or (str(note) if 'benchmark' in str(note).lower() or '基准' in str(note) else 'UNKNOWN：元数据未明确是否保留为 benchmark。')))
