# R2 DATA_ENGINEERING

Source Chat: 6a9d94c3-d250-83e8-9ef0-24d6498281ea
Actual response; model setting not independently verified. Markdown trailing whitespace normalized.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R2-DATA_ENGINEERING-RESULT
REPLY_TO: C2C-20260907-R2-DATA_ENGINEERING
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: DATA_ENGINEERING
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

**DISPOSITION: PROCEED_SMALL_PAPER_WITH_CONDITIONS / BLOCK_ALPHA_PROMOTION**

本轮已把新增 `EVIDENCE_CORRECTION` 一并纳入裁决。R1阶段关于两篇2026论文的旧解释全部撤回：`2607.02823 v3` 的 **0.198%不能称24小时毕业率**；`2607.02795 v3` 的旧“买方约+132%、资金约+136%”不能继续引用，修订后的买方关联约 **+16.1%**，资金 **+6.3%且区间包含0**，placebo约+189.6%是作者用于诊断估计偏差的结果，不是支持钱包alpha的有效负对照。BONK 的发行/首交易 t0 也继续视为**未裁定**，不使用 2022-12-08 或 2022-12-25 任一日期作为策略事件时间。

## 一、R2核心裁决

当前完成的全历史统计改变了R1时的信息状态，但**没有改变核心经济结论**：

截至 `2026-09-06T16:46:50.205259Z`，最终资金期仅自然运行 **1.28936小时**。虽然已经有 6,681 个完整闭环，但这些闭环高度共享 token、cohort、行情路径，而且不少策略具有共同父机制。**账户闭环数不是成熟时间，也不是独立机会数。**

当前最终期闭环结果：

| 指标 | 当前结果 |
|---|---:|
| 闭环 | 6,681 |
| 闭环 PNL | -40,134.18U |
| 胜率 | 17.00% |
| PF | 0.231 |
| expectancy | -6.01U |
| median | -4.16U |
| P05 | -20U |
| P95 | +13.66U |
| 持有中位数 | 11.39分钟 |
| WRITEOFF | 1,932 |

这足以证明**当前组合在这个极短窗口的原始Paper表现很差**，但还不能合理推出“16个新机制也会失败”，更不能把92个达到纯数量标签的arm写成成熟独立实验。

所以我支持：

**允许机制差异明确、资源成本低、严格前向的小额Paper；禁止任何alpha、晋级、扩大资金或“终极策略”盈利宣称。**

---

# 二、对其他R1的交叉反驳

我实际读取了 `R1_CAUSAL_STATISTICS.md`、`R1_STRATEGY.md`、`R1_MICROSTRUCTURE.md`。其中至少有以下四处需要限定。

### 1. 对 Strategy R1：“transition / sequence 比单帧阈值更值得继续研究”

**方向同意，但表述过强。**

历史目前只能说明若干单帧/存在性规则表现很差，以及 continuation-failure 有轻微“少亏”迹象：

`l0_continuation_failure candidate-control` 同闭仓交集91个，差值约 `+21.79U`。

但候选和control本身仍约：

- candidate `-642.68U`
- control `-648.07U`

因此现有证据只支持：

> sequence 是合理的待证伪设计空间。

不支持：

> sequence 已经优于单帧机制。

这一区别会直接影响16候选是否可以进入Paper：**可以实验，不可给优先级资本奖励。**

---

### 2. 对 Strategy R1：“exit与post-entry state占至少一半研究预算”

我不支持把“至少一半”写成硬资源比例。

原因是当前最终期仅1.29小时，且新候选中的多数入口本身还没有自然前向数据。现有统计确实证明 conditional runner 和当前 profit-lock candidate 没有优势：

- `l0_profit_lock` paired delta `-62.54U`
- `experiment_conditional_runner` paired delta `-84.84U`

所以“退出值得研究”成立，但**不能因为旧Broad有盈利回吐，就把资源配置硬定成50%以上**。更合理的是共享同一L0帧，同时跑少量entry序列与少量exit对照，谁的自然覆盖成熟得快就先获得证据。

---

### 3. 对 Microstructure R1：“约+8.33%成本带后，主要寻找+15%～+30% impulse”

**成本算术正确，15%～30%不应成为默认入场阈值。**

`1.04 / 0.96 - 1 = 8.333%` 是当前轻量Paper的名义回本带。

但把它推成：

> 候选应该寻找+15%～+30% impulse

仍然是研究假设，不是当前数据支持的最优阈值。如果策略只有在事后能识别15–30%右尾才成立，很容易重新进入winner-selection。

R2允许使用“必须出现足够跨成本的状态变化”这一**设计原则**，但不建议16候选统一添加15%、20%、30%固定门。

---

### 4. 对 Causal R1：“≥30 terminal unique opportunities、≥15 dates可作最低研究checkpoint”

统计原则同意，但对当前快速Meme系统而言，**不应把它变成候选启动前置条件**。

它更适合：

`Paper启动以后 → 是否值得正式比较/资本复审`

而不是：

`没有30个历史机会 → 不允许创建新候选`

否则新机制永远无法得到严格前向数据。

因此我明确区分：

- **候选部署门**：机制清楚、输入已存在、严格前向、成本有界、不会污染主系统；
- **盈利晋级门**：独立机会、日期、robustness、tail、工程清洁等成熟要求。

---

# 三、8个现有代表的R2裁决

| 机制 | R2裁决 | 数据/工程理由 |
|---|---|---|
| `l0_continuation_failure_candidate_v1` | **KEEP / Paper继续** | 当前paired差值+21.79U，只能称少亏线索；输入完全来自已有L0，无新增请求，适合作为退出实验 |
| `l0_profit_lock_candidate_v1` | **KEEP AS NEGATIVE CONTROL / 不提升** | 当前paired `-62.54U`；机制并未得到优势，但这是有价值的反证，不能因结果差删掉 |
| `observed_cycle_reset_reacceleration_v1` | **KEEP CONDITIONAL** | 机制与single-wave/new-episode不同；受80帧/20分钟历史窗口限制，缺足够完整episode就WAIT |
| `volatility_scaled_depth_flow_momentum_v1` | **KEEP BUT RENAME/SEMANTIC CLARITY** | “pressure”只是L0聚合量代理，不得在统计报告里叫真实资金流；无需新增资源 |
| `experiment_participation_candidate_v1` | **KEEP CONDITIONAL / 5U** | 已解析地址扩散可以研究，但地址≠人、覆盖不完整；不能成为全局硬门 |
| migration amount absorption | **KEEP CONDITIONAL** | 有真实迁移/金额输入时机制独立；无amountful覆盖时不能退化成“迁移即买” |
| `clone_liquidity_leader_v1` | **KEEP** | 冻结候选集后比较同题材竞争是独立机制；必须禁止事后补赢家和symbol-only匹配 |
| `observed_set_relative_resilience_candidate_v1` | **KEEP** | 只声称“已观察集合相对韧性”，不冒充市场regime；共享snapshot即可 |

**结论：8个都无需删除。**

但其中 wallet/participation、migration 属于**条件型Paper**，输入缺失不是失败。`l0_profit_lock` 当前反而应该被保留，因为删掉表现不佳的已部署候选会产生选择偏差。

---

# 四、8个拟新增机制逐项审查

这是R2最重要的部分。

| 新候选 | 裁决 | 是否与旧机制重复 | 最小实现/时序约束 |
|---|---|---|---|
| 突破后接受 | **APPROVE 5U** | 与 sustained breakout 同族，但“跨成本位移→新价格区至少2个独立帧接受”具有行为差异 | 必须使用严格较后的独立帧；duplicate frame不能计2次；不能拿同一provider缓存刷新当接受 |
| 窄幅压缩释放 | **APPROVE 5U** | 与旧 flat-compression shadow 有血缘，但旧者非当前等价Paper入口；可作为严格前向Paper版 | 必须真实拥有连续基线；冷启动/断采不能补成低波动；不新增历史回填 |
| 回测区域承接 | **RENAME + APPROVE** | 与 pullback/reclaim 高度同族 | **禁止“回测”命名**，建议“突破区回踩承接/Breakout-zone retest acceptance”；要求冲击→回撤→两次区域保持→后续再启动 |
| 抛压减弱反弹 | **REVISE / APPROVE CONDITIONAL** | 与 panic reclaim、support risk 有重叠，但可通过“sell-count share连续下降+低点抬高”区分 | 当前buy/sell count不是金额流；绝不能称“抛压金额减弱”。volume为滚窗，禁止做错误逐帧差分 |
| 双次下探吸收 | **MERGE / 不建议独立新增ID** | 与回踩承接、panic reclaim高度重叠 | “两次低点未击穿+收复”可以作为**同一反转状态机的一个状态**，没必要再造独立策略账户 |
| 流动性先增后重估 | **APPROVE 5U，强语义限制** | 与 liquidity leader不同；它研究单币时间序列的liq-leading-price | Dex/GT的USD liquidity随token价格变化，本身存在机械耦合；必须要求“价格近似平稳时liq变化”，且名称不能叫LP净流入 |
| 首冲后缩量再启动 | **APPROVE 5U** | 与 cycle-reset有关，但这里是“保持高位的缩量整理→活动重新扩大”，cycle-reset是深重置后新wave，可保留二者 | rolling volume不能做逐笔delta；必须对真实观测窗口定义冷却，不用缺采样表示缩量 |
| 阶梯式趋势持有 | **REVISE / 先做EXIT OVERLAY，不新建独立entry** | 与已有持仓runner/peak-drawdown关系太近 | 建议共享一个已存在entry，把“两段抬升+更高低点”作为是否延续持仓的exit treatment；避免entry×exit笛卡尔积 |

所以8个新机制不应原样变成8个新策略ID。

我的建议是：

**新增6个真正独立候选 + 1个合并状态 + 1个exit overlay。**

这比机械凑16个更符合本轮“机制多样性”要求。

---

# 五、建议最终R2组合：14个机制，而不是硬凑16个

保留已有8个，同时新增：

| 新增行为机制 | 建议形式 |
|---|---|
| Breakout acceptance | 5U独立Paper |
| Compression release | 5U独立Paper |
| Breakout-zone retest acceptance | 5U独立Paper |
| Sell-count-pressure easing rebound | 5U条件Paper |
| Liquidity-leading repricing | 5U独立Paper |
| Post-impulse cooldown reacceleration | 5U独立Paper |

另：

**双次下探吸收**并入 `breakout-zone retest / panic-reclaim` 状态机，不新建账户。

**阶梯式趋势持有**作为一个共享入口上的 `exit overlay`，不要变成独立entry策略。

这样最终是 **14个机制代表**，落在用户要求的10–20范围内，而且不会人为制造重复样本。

---

# 六、底层需要先满足什么，哪些问题不应该再阻止Paper

这里必须严格区分两类BLOCK。

## A. 只阻止盈利宣称，不阻止小额Paper

以下问题**不能再作为“什么都别部署”的理由**：

| 问题 | 为什么只BLOCK PROMOTION |
|---|---|
| 当前最终期只有1.29h | 不成熟，但新增严格前向实验恰恰需要从现在开始积累 |
| 历史大部分策略亏损 | 不能证明新的状态序列机制必然失败 |
| v22/right-tail极度winner集中 | 阻止引用旧漂亮PNL，不阻止新frontier实验 |
| 普通Paper不是amount-specific真实执行 | 用户已明确选择轻量Paper；只限制收益解释为模拟 |
| 钱包/参与地址覆盖不全 | 条件型candidate可以WAIT，不能冒充全覆盖 |
| migration输入稀疏 | 只在真实输入命中时参与，零交易不是失败 |
| external论文不能证明alpha | 外部证据本来就只用于机制，不负责策略晋级 |
| TOKEN_PRECURSOR_EVIDENCE仍在生成 | 不能引用其结果选阈值，但不妨碍先冻结无后验参数的L0机制 |

---

## B. 真正应该BLOCK某候选部署

只有下面这些会让我阻止某个新候选上线：

| 阻断项 | 具体原因 |
|---|---|
| 候选必须使用未来帧、ATH、后来winner身份才能判定 | 直接因果泄漏 |
| 所谓“两个独立帧”实际可由duplicate/cache frame满足 | 会制造假持续性 |
| liquidity=NULL/负数可以被当作增长、恢复或安全 | 已有确定工程反例 |
| 使用兄弟池/另一交易表面替代原池连续序列 | 池身份错误会改变策略经济语义 |
| 用滚动5m volume直接相减伪造逐笔资金流 | 指标单位/窗口语义错误 |
| 把buy/sell count叫金额净流 | 特征名与真实输入不一致，形成策略解释污染 |
| 新策略需要大量新增RPC/API请求、抢held/exit资源 | 用户目标明确要求后台退出/持仓优先 |
| 没有真正不同的行为，只是已有规则换名字/阈值 | 增加相关账户数但不增加研究信息 |
| 冷启动缺基线却用0或静默默认值填充 | 会把数据缺失伪造成交易状态 |
| 同一snapshot同时作为trigger和fill | 违反现有严格后帧Paper语义 |

只要Codex实现时不触犯这些边界，我不支持用“历史还不成熟”为理由阻断全部小额Paper。

---

# 七、数据/资源约束

R2草案声称新L0机制：

- 不新增外网请求；
- 共用最多80帧；
- 时间跨度上限20分钟；
- 5U；
- 最多4仓。

**这一资源合同我支持。**

但有三个具体工程限制需要Codex执行时冻结。

### 独立帧定义

“两个帧”“两次下探”“两段上涨”必须至少满足：

- `snapshot_id`递增；
- `observed_at`严格递增；
- 同 canonical original pool；
- duplicate frame被排除；
- 不把相同缓存代的重新接收当独立市场变化。

项目历史已经发生过 duplicate frame 清空 pending signal 的缺陷，所以这不是理论性防御。

### 滚动窗口语义

已有字段里的：

- m5 volume；
- m5 buys/sells；
- h1 volume；

大多是供应商滚动聚合。

因此候选可用：

`当前window水平 / 多帧趋势`

但不能把：

`V_t - V_{t-1}`

自动解释成该两帧间真实成交金额。

### liquidity单位

`liquidity_usd` 是USD计价的池流动性指标，不是LP实际新增USD。

当token价格变化时，它可能机械变化。

所以“流动性先增后重估”至少应要求：

**价格在窄带内时 liquidity 明显改变，之后才观察price confirmation。**

否则候选可能只是：

> price涨 → liquidity_usd机械涨 → 再拿liquidity涨解释price涨。

---

# 八、外部证据纠错后的R2影响

`EXTERNAL_CORRECTIONS.md` 对16机制的影响主要有三点。

### Pump.fun毕业率

旧解释：

> 0.198%约为24h毕业率，较过去下降约3倍。

**撤销。**

最新版研究只覆盖发行后约6分钟，因此：

- 不能用0.198%设置“绝大多数24小时必死”的regime；
- 不能据此提高统一pre-entry gate；
- 不能用未在6分钟毕业直接定义失败。

这反而支持保留**高召回 + 快速淘汰**以及**新episode**研究，而不是预先过滤绝大多数币。

### 钱包效应

旧大幅提升数字撤销后，钱包/participation机制的地位应**下降为条件型增强实验**。

最新版可支持的只是：

- 买方数关联有正方向；
- 资金流结果不排除0；
- placebo显示估计有严重偏差风险。

因此我不同意把 wallet confirmation 放入主干或 universal gate。

当前草案只把 `experiment_participation_candidate_v1` 保留为条件型候选，这个尺度合适。

### BONK

BONK的2022-12-08与2022-12-25冲突说明一个典型问题：

**“发行日期”本身不是唯一point-in-time事件。**

以后外部案例必须分清：

- mint/create；
- distribution；
- first pool；
- first observed trade；
- official announcement；
- local first-seen。

所以BONK不应被用来训练“发行后X分钟”的当前策略阈值，直到t0定义和一手证据明确。

---

# 九、R2对盈利宣称的明确禁止

即使这14个机制全部立即进入5U Paper，也仍然只能叫：

**strict-forward hypothesis experiments**

不能叫：

- final alpha；
- profitable strategy；
- validated strategy；
- superior strategy；
- long-term winner；
- live-ready；
- 终极策略已证明。

尤其当前唯一最终期原始闭环正PNL arm：

`watched_wallet_confirmed_entry_control_v1`

只有：

- 39闭环/39 token；
- +4.83U；
- PF 1.10；
- median -0.264U；
- 去最好3笔变 `-29.61U`。

这甚至不足以证明那个control本身有alpha，更不可能证明wallet信息有效。

---

# 十、允许小额Paper后的最低研究输出

每个新增候选至少应以后续自然数据同时报告：

`unique opportunity N / account N / terminal / open-right-censored / token N / 日期数 / candidate-control paired N / PNL / median / trimmed mean / P05 / PF / writeoff / Top1-Top3 concentration / remove-best-token robustness / engineering contamination / unknown coverage`

特别是：

**remove-best token 优先于仅remove-best trade。**

v22已经给出非常强的实际教训：

- 表面总PNL `+7.316M U`
- 单一token占正token PNL `94.14%`
- 去最佳token后变成 `-232,664U`

只删最好交易仍能留下巨大正数，根本无法暴露同一token被多账户、多episode重复放大的问题。

---

# 十一、最终R2裁决

**允许进入小额Paper：YES。**

条件是：

- 新机制只用已有point-in-time L0；
- 5U；
- 最多4并发；
- 不新增外网请求；
- 严格独立后帧；
- 不冷启动填0；
- 原池身份；
- NULL/负liquidity fail-closed/WAIT；
- 不把滚动聚合伪造成金额流；
- 不复制等价策略；
- 不重置任何旧账户；
- 不改旧历史；
- 不晋级Live。

**建议实际新增：6个新Paper候选 + 1个已有入口的阶梯趋势exit overlay；双次下探吸收并入retest/reclaim状态机。**

因此“8复用+8新”的原草案应收敛为：

**8个既有代表 + 6个真正独立新L0机制 = 14个核心机制代表，另1个exit overlay作为对照，不单独扩大entry样本。**

这比注册16个看起来整齐的ID更符合实际统计与工程约束。

---

## 实际读取路径

本R2实际通过 `@笔记本量化MCP-官方隧道` 只读读取：

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R2_DESIGN_QUESTIONS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/HISTORICAL_STATISTICS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/HISTORICAL_EVIDENCE_MAP.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/EXTERNAL_EMPIRICAL_EVIDENCE.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/EXTERNAL_CORRECTIONS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_CAUSAL_STATISTICS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_STRATEGY.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_MICROSTRUCTURE.md`
- 项目 `AGENTS.md`

未运行新的大SQL，未改代码、Runtime或数据库，未读取秘密配置，未使用仍在生成的 `TOKEN_PRECURSOR_EVIDENCE.md` 得出任何特征优劣结论。

**R2 DATA_ENGINEERING最终结论：`PROCEED_SMALL_PAPER_WITH_CONDITIONS / BLOCK_ALPHA_PROMOTION`。**

最重要的裁决不是“当前亏，所以别实验”，而是：**当前亏损已经足够否定任何盈利宣称，却没有理由阻止低成本、严格前向、机制不重复的新实验开始积累真正可用的证据。**
