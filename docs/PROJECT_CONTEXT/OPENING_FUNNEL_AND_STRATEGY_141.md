# 开仓漏斗、时间窗口与策略落地141

用户要求多Agent核对开仓少的原因，并把此前尚未接通的可执行机制封装为策略。当前根执行者保持唯一生产writer；两名Terra只读分工检查窗口/收据及附件实现覆盖，未建立第二写入者。

源提交 `a9a33f4` 已推送，并在2026-09-10T10:41:59.746987Z启动的PID40216加载；Web也通过现有启动器独立重载。此次实际成功加载同时覆盖此前763ccce的native诊断/漏斗。140中的最后一次进程审查拒绝是历史事实，不再代表当前加载状态。

## 结论与修复

开仓少不是一个统一的“阈值太严”问题。逐笔收据区分如下：

| 检查 | 当前证据 | 处理 |
|---|---|---|
| 安静期窗口与取样不匹配 | 旧quiet confirmation只保留最后3个至少15秒间隔点，正常跨度约30秒，却要求跨度至少120秒；近期2656条评估为baseline_span_not_met | 改为保留满足原120秒要求的最短完整后缀，逐个检查内部点；不降低120秒、安静度或其他门槛 |
| 待处理信号被批次覆盖 | Runtime按token/pool整个替换pending，忙碌时后续其他arm信号可以覆盖尚未投影的一次性机会 | 按arm合并，仅更新同arm；旧信号按原recorded_at独立过期，绝不续命或回填 |
| 安全等待过期 | 两个RH历史机会的检查在约1.5–2秒完成，但usable/strong facts为空，之后到90秒过期 | 保持UNKNOWN/等待；延长TTL不能把空报告变成安全事实，不放宽安全门 |
| 重启后重复看到旧信号 | 冻结六个Dex信号中五个已有消费/过期收据，只有一个是新机会且确有BUY94780 | 不把五个旧key算作五笔漏单，不重复买入；新增唯一arm+decision-key分层计数 |
| 短窗口是否不可达 | 实际watch约15秒起调、消费约2秒；新进程3611个处理帧中3073次已有30秒窗口，2728次有60秒窗口 | 未发现全局秒/分钟误用；不统一扩大窗口或把90秒发现流伪装为连续行情 |
| 再发现观察席位 | 旧窗口26episode、16basic_valid、13bucket_full且chain=10、3pattern observations | 真实容量约束，保留既有bounded probe；本次不扩大watch/请求频率 |
| 热门/有机机制样本少 | 近期ready稀少、部分hot同龄peer不足、部分流量/安全字段未知 | 分别暴露缺字段、窗口、peer、规则就绪原因；不以提高pass率代替机制验证 |

`evaluation_reasons.json`是有界评估行统计，不是独立机会数。子Agent的`cadence.json`仅代表持久化发现快照子集，不能反推所有被动watch回调缺少短轨迹。当前真实Engine窗口计数明确排除了这个过度推断。

## 新策略：dex_regime_recovered_runner_v1

一个新增5U/max2策略，接入现有cohort/common safety/严格下一原池帧执行与账本；max2包含待安全授权的预约，不另外建立BUY框架。旧策略和老router合同均未覆盖。

固定路由顺序：已验证再唤醒 → 冻结事件绑定 → clone共识 → 首次回撤韧性 → 早期热启动 → 压缩突破 → 安静加速 → 活动领先价格 → 有机流 → 短观察有机流。只复用当时真实source signal及其冻结key、原始可得时间和池身份，记录各分支SELECTED/已有但低优先/无有效信号。未知无信号不买。没有独立冻结规则的LATE_MOMENTUM明确不买；DEAD不买。合成BUILDING留给原1U精确执行策略，DISTRIBUTING/硬不可卖不得进入这个5U普通路由。

退出保留−20%硬止损、+30%激活/15%追踪、基础15分钟。只有实际部分SELL结算后已经回收原始debit且仍有剩余runner，才允许60分钟软上限；未回本仓不会因理论可回收或Agent观点延长。采用现有“最小实际净回本且保留至少半仓”的计算与真实fill后high-water；不新增固定TP/半仓目标价或Agent调用。硬止损、流动性与真实执行限制始终优先。

两个自然新仓都已验证：

| cohort | 链 | signal recorded UTC | 实际BUY UTC | 入场snapshot / fill | 金额 / 当时状态 |
|---|---|---|---|---|---|
|94786|BSC|10:44:16.715936|10:44:26.813133|2698973 / 94361|5U / open|
|94787|Solana|10:44:17.235662|10:44:29.553641|2698978 / 94362|5U / open|

两者路由均为NEW_QUIET；source signal晚于新activation，BUY是后续真实帧。安全收据为可用事实下的`BUY_AUTHORIZED_UNKNOWN`，不是全面安全PASS。两笔均未实际回本/终局，不能宣称盈利或长持机制已被自然验证。

## 检查、加载与资源验收

28个不同的针对性测试通过：pending忙碌多批/过期、原120秒quiet内部点、固定路由/合成隔离、唯一机会计数、activation、pending容量、真实producer→安全等待→严格后帧BUY→实际partial回本→runner，以及未回本max-hold、硬退出优先。复用原Dex和synthetic实际Store链路测试；未重跑已通过的native VM/RPC证明。`git diff --check`通过。

注册id311，snapshot2698311，activation2026-09-10T10:41:52.695632Z。只新增这一个policy row；原310条addition逐字段相同，25条registration逐字段相同，fixed funding restoration仍0。当前funding保持`chain-meme-trader/funding-20260906-v002-final-1000`，Paper=true，Live locked；226/254/255继续forward enabled。新增策略沿用现有Paper账户初始资本合同，没有重置旧账户。初始审计使用的`paper_funding_activations`表名不存在，不能给它伪造hash比较；实际`chain_meme_trader_paper_funding_activations`只有既有2026-09-04激活记录，无本次资金激活。

10:47:41Z验收已运行约5分42秒。相同类型有界窗口、当前3个unique held，前后负载并非实验配对，数字只表示未触发回滚护栏：

| 指标 | 加载前10:41 | 加载后10:47 |
|---|---:|---:|
|held_fetch p95|2.120s|1.984s|
|held_apply_exit p95|53.1ms|61.6ms|
|passive wait p95|2.278s|2.045s|
|passive dropped quotes|0|0|
|Dex PoolTimeout / ConnectError|0 / 0|0 / 0|
|flat task p95|5.800s|5.007s|
|flat selector p95|0.664s|0.674s|
|flat actual interval p95|6.212s|5.698s|
|pattern observer actual interval p95|15.451s|15.392s|
|token hydration p95|5.738s|4.749s|

held_fetch本进程失败0；进程前累计2不可与新进程0解读为故障率改善。Gecko RH已有429仍存在，未加请求/绕过backoff。新公共漏斗3个独立BUY cohort，其中2个为新router；不能把账户fanout当独立机会。新增signal_opportunities10个唯一arm+key，各stage非互斥；Engine计数是处理帧，不能转成币级胜率。pending_signal_preserved自然0，修复目前只有确定性回归证据，不能宣称挽救了多少订单。

冷启动曾有约55秒的FlatSelector全历史投影重建，之后selector p95恢复0.674秒；它不持有Store锁做完整扫描。独立只读检查确认现有索引已覆盖查询，但没有持久化投影可以直接恢复。要消除后续冷启动需新增一致性checkpoint及重放测试；本次未用缩短历史/缓存过时membership冒充性能修复。这是明确保留的启动延迟问题，不是已修好的持续性能瓶颈。

## 前序附件实现覆盖与真实边界

| 范围 | 当前交付 |
|---|---|
|Dex衍生向量/五类入场/三类退出|139已实现并加载；141增加缺字段/短窗口/peer分层与两处正确性修复；旧合同未重注册|
|完整普通场景组合与回本runner|本次一个新策略已注册/加载/自然两笔BUY；原三个模式router仍独立保留|
|organic/clone/event/synthetic119–138|真实producer/common安全/下一帧/SELL/no-reentry已接通，合成精确sell证明仍是资金化必要条件；无unsigned114复活|
|Pump SOL原生|proof、Token2022 metadata controls、cash assembler、当前账本、held任务、capacity部分SELL/canonical handoff已加载；94747自然部分回款0.7328U，剩余仍OPEN/UNKNOWN，不能把容量不足伪造核销|
|Pons与其他未证明原生类|DATA_BLOCKED；本次未重复已失败的来源验证或假装可执行|
|Agent/叙事|现有value/credible-event admission、两槽Scout/Verifier、UNKNOWN后续验证与实际回本才延长的规则已加载；没有强制制造调用或新正向自然证据|
|16/23案例与匹配|已完成描述、既有匹配、严格保存收据与可用端点核对；保存数据无合格6h覆盖，不能伪称全面验证或把UNKNOWN当亏损|
|ModeChat|既有实现/本机安装保留；本次只更新一个当前checkpoint。新浏览器Chat、模型、Project memory仍未实际验收，不能阻塞交易也不能虚构完成|

证据：`data/research/opening141/{signal_receipts,evaluation_reasons,cadence,before_load,after_load,early_performance,acceptance,invariants_and_natural}.json`。均为有界本地读回，研究数据未加入Git。盈利、未来容量和不存在的历史观测不能通过实现补造；本次交付的是修好的因果链路、可交易策略和可区分原因的前向分母。

本次唯一语义checkpoint为revision15，digest `369e3fb66af4eb784cbfc66a8c279f1ad2a994925bb747da9de5eafbb68252bc`。实际本机resume读回CONSISTENT，owner codex/epoch0、无stop fence；不是新Chat或Project-memory验收。不因后续ACK重复提升revision。
