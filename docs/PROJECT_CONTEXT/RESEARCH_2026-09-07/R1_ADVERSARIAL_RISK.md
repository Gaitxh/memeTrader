# R1 ADVERSARIAL_RISK

Source Chat: 6a9d94dd-2eb8-83e8-ac4b-bdfc14bd49a1
Retrieved: 2026-09-07 Asia/Shanghai
Actual Chat response; model self-description is not host-verified model metadata.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R1-ADVERSARIAL_RISK-RESULT
REPLY_TO: C2C-20260907-R1-ADVERSARIAL_RISK
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: ADVERSARIAL_RISK
DISPOSITION: REVISE
BLOCKS_RELEASE: true
MODEL: GPT-5.6 Sol；Chat侧实际推理档位无法独立验证，标记 **未核验**。
SENSITIVE_DATA: NONE

### 1. 独立审查结论

R1 的反方结论是：**目前没有任何历史 Paper“漂亮结果”应直接获得终极策略资格。**

这不是说历史全部无效，而是当前项目自己已经记录了足够多的工程、执行、样本依赖和行为重复问题，使“某策略赚过钱”远远弱于“该机制拥有独立、严格前向、扣成本、可实现且跨 regime 的正期望证据”。

同理，也**不赞成因为当前某些策略亏得很惨就把方向全部否决**。必须先区分：

`机制真的差`
vs.
`共享错误/数据污染`
vs.
`错误执行模型`
vs.
`重复策略复制同一失败`
vs.
`市场 regime 切换`。

因此我的意见不是“把门控加严”，而是：**显著降低模板重复，增加机制正交性，并用强反事实对照主动杀策略。**

---

# 2. 项目事实

以下来自我本轮实际读过的项目材料，不来自其他 reviewer。

**事实 A：122 V002 本身并非 122 个独立假设。**

`STRATEGY_V002_EXECUTION_TABLE_2026-09-06.md` 明确写明：

- 32 个旧 reawakening 槽位曾只共享 **同一个 cohort 10237**；
- V002 后它们仍统一使用一个 `flow_burst` 型入口，主要比较四类退出；
- 17 个证据不足臂被替代为 L0 信号；
- 名义上 7 个方向，`quality_gate` 与 `early_quality` 实际判定相同，因此只有约 **6 种实际形式**；
- 多个臂仍只是参数/退出变体。

所以：

> “32 个策略都有效”不能形成 32 票证据。

它最多可以形成“一个 entry family 下若干 exit treatment”的实验。

---

**事实 B：历史已经发生多种足以污染策略评价的工程故障。**

`CURRENT_OBJECTIVE_AND_PLAN.md` 明确记录了至少：

- 主源有正价格但 `liquidity=NULL` 曾被错误算作成功；
- 不完整响应曾覆盖旧完整原池行情；
- BSC Gecko 曾返回负 reserve，并曾造成错误 BUY；
- 共享 SQLite mutex/GIL 锁顺序导致整个后台停滞；
- 已识别 **81 笔负流动性工程污染交易**；
- 部分历史错误核销已得到确认；
- 仍存在历史缺原始证据而不能确定真实结果的案例；
- Robinhood 原池覆盖仍有明显缺口；
- 免费源 429、缓存和数据陈旧持续存在；
- 账户估值存在 incomplete/unknown。

所以任何跨这些故障期汇总出来的高 Sharpe、高 PNL、高 win rate，如果不按 contamination frontier 切开，我默认：

**NOT DECISION ELIGIBLE。**

---

**事实 C：Paper 不等于可成交结果。**

范围文件明确规定：

- 当前是轻量 Paper；
- 核销 SELL intent 不等于实际链上成交；
- current market price ± 固定 adverse slippage 不是 amount-specific execution proof；
- 缺值、失败、限流不等于池死亡。

因此一个策略即使 Paper PNL 很漂亮，也存在一个致命反方问题：

> **它的赚钱是否集中在真实最难卖的那些尾部币上？**

如果是，那么漂亮 PNL 可能正是执行模型最乐观的区域。

---

**事实 D：当前资金期不能被倒灌到历史。**

当前生产合同是默认：

- 独立 1000U；
- 通常 20U；
- BUY 4%；
- SELL 4%；
- extra 0U；
- 原池 floor 1000U。

但历史曾采用不同门槛/执行语义。

因此将所有历史统一重算成当前规则后做排行榜，会制造伪历史。

每个版本只能依据**当时冻结的 contract**评价。

---

# 3. 本轮“统计发现”

**没有。**

`HISTORICAL_EVIDENCE_MAP.md` 和 `HISTORICAL_STATISTICS.md` 在 `REVIEW_SCOPE.md` 中明确标为 **生成中**。

我没有读取、引用或暗示已经知道其结果，也没有运行大规模 SQL。

后续若其结果与本 R1 假设冲突，应以完成后的冻结统计证据重新裁决。

---

# 4. 外部证据

这里与项目事实严格分开。

### 4.1 “成交很多”本身不是健康需求

2026 年 Pump.fun 研究对新币成功进行建模，表明早期市场行为确实具有预测信息，但这种信息要结合 bonding-curve 状态和结构变量，而不是简单把成交笔数/成交量理解为需求。citeturn859236academia24

另一项 2026 年覆盖 832,941 次 Pump.fun launch 的研究还发现，不同时间窗毕业率发生了很明显的 regime shift：其 2026 年窗口毕业率显著低于论文引用的 2025 年样本。citeturn859236academia25

**反方含义：**

固定的：

`m5 trades >= N`
`m5 volume >= X`

很容易学到特定日期的 regime，而不是结构性 alpha。

---

### 4.2 暴涨币本身高度受到操纵选择偏差污染

USENIX Security 2026 对 34,988 个 Meme Token 的跨链研究发现，>100% 高收益币中 **82.89%** 出现其定义的人工增长迹象，包括 wash trading 和 liquidity-pool price inflation。citeturn859236search1

论文进一步识别到大量 circular/wash-volume 模式。citeturn859236search26

因此：

> “研究所有暴涨币共同特征”如果没有普通/失败/暴跌对照，非常容易学到操盘者制造的表面特征。

这尤其攻击：

- raw volume；
- raw tx count；
- buys/sells；
- price acceleration；
- apparent buyer breadth。

---

### 4.3 SOL 新币尾部风险非常早发生

2026 年 8 月一项覆盖约 640 万 Solana Token 的研究报告，大量 rug 特征在发行后一小时内出现，并尝试仅使用前 5 分钟信息识别风险。citeturn859236academia27

这支持项目继续研究**快速风险状态变化**，但不证明任何具体 ML 模型能直接移植到当前系统。

---

### 4.4 当前轻量 Paper 的最大反方仍然是 price impact

Uniswap 官方文档明确区分：

- price impact：自身交易相对可用 liquidity 对成交价格造成的移动；
- slippage：提交与最终成交之间的额外变化。

流动性越薄，相同交易量的 price impact 越大。citeturn859236search0turn859236search2

所以固定 4% adverse slippage 可以作为统一 Paper contract，但：

**不能把它称为真实可实现价格模型。**

这也是为什么终极策略晋级必须增加独立的“execution plausibility”检查，而不是修改当前普通 Paper 引擎。

---

# 5. 我要求用来“推翻漂亮策略”的 9 个对照

任何终极候选，至少应面对下面对应的反证，而不是只展示自己的 PNL。

1. **行为等价对照**
   完全相同 entry+exit+state transition 的 ID 合并为一个 treatment。

2. **同 cohort 聚类对照**
   20 个策略同时买一个 Token，只能算一个市场事件，不算 20 个独立胜利。

3. **时间 regime 对照**
   至少按 UTC 时段、日期和市场活动 regime 分层；若收益只存在于极窄时间窗，降级。

4. **链独立对照**
   SOL/BSC/RH 不直接混合；只能说“机制可迁移”或“不可迁移”。

5. **低成本假胜利对照**
   对盈利结果询问：如果退出价格恶化额外 2–5%，alpha 是否完全消失？

6. **延迟对照**
   Signal 后额外 +5/+15/+30 秒执行仍有 edge 吗？若 +5 秒即死亡，这是极高 latency sensitivity。

7. **普通币/失败币 placebo**
   相同 token-age/liquidity/regime 的非暴涨 Token 是否也大量触发？

8. **触发特征置换对照**
   保留 market regime，打乱真正 treatment feature；若 performance 类似，说明条件可能没有提供信息。

9. **入口/退出拆解**
   好 PNL 究竟来自 entry alpha，还是一个普遍更好的 exit？必须做 entry×exit factorial，而不是把它包装成新“完整策略”。

---

# 6. 严格前向可证伪条件

候选不应设置“成功条件”而没有“失败条件”。

我建议每个机制预注册以下死亡条件：

**A. Coverage death**

触发机制有 >50% 机会因为输入缺失无法判定，则不能作为主力策略。

**B. Execution death**

Paper 盈利主要来自低 liquidity / stale mark / unknown route 尾部，则不晋级。

**C. Dependence death**

去重成 unique token episode 后有效样本缩水 >80%，不得继续使用原 n 声称显著性。

**D. Regime death**

只在单日或单个非常窄 regime 为正，跨 regime 转负，则标 regime-specific，而不是 universal。

**E. Cost death**

仅取消一部分乐观执行假设就让 expectancy ≤0，则不能进核心。

**F. Placebo death**

matched non-winner/control 同样大量触发，说明它只是“市场活跃检测器”。

**G. Timing death**

Signal 至实际可决策/可成交存在未来帧泄漏，整个 cohort 作废，不允许修时间戳后保留 PNL。

**H. Capacity death**

一个策略获得的理论收益只能在 1–5U，而 20U 规模 price impact / liquidity 已不可信，则只能保留 small-capacity arm。

---

# 7. 建议保留的 16 类机制多样性

这些是**研究候选机制族**，不是已经证明赚钱，也不是让 Codex 现在全部实现。

重点是避免再制造 16 个 `volume >= X` 变体。

### 1. Capital-Progress Efficiency

不是“成交量大”，而是：

> 单位交易/单位时间推动真实曲线资本前进的效率。

区分真实资金推进与 churn。

### 2. Unique-Buyer Expansion

关注独立参与者增长速度，而非 buy count。

核心反证：同钱包/关联钱包拆分是否解释全部增长。

### 3. Buyer Quality Transition

不是静态“聪明钱包”，而是：

早期随机参与者 → 后续有历史质量的钱包是否自然接力。

### 4. Seller Absorption

大量真实卖压出现后，价格/流动性没有同比恶化。

这是 demand resilience，而不是更严门控。

### 5. Liquidity Elasticity

比较：

`Δprice / Δnet flow`

识别价格上涨究竟需要大量真实资金，还是几美元就能把价格推飞。

后者可能恰恰是 LPI 风险。

### 6. Churn-adjusted Momentum

用成交额减去疑似往返/circular churn 后再定义 momentum。

### 7. Breadth-vs-Concentration Divergence

价格涨 + buyer breadth 扩散 = 一类；

价格涨 + ownership/flow 越来越集中 = 另一类。

二者应使用不同 exit。

### 8. Post-Impulse Survival

第一次急冲之后，不追最高速度；

研究 impulse 后第一次回撤能否：

- 守住 liquidity；
- 保持参与者；
- 恢复净买流。

### 9. Failed-Breakout Reclaim

第一次 breakout 失败但没有结构性死亡，随后重新收复关键区域。

它和“继续追涨”具有完全不同状态机。

### 10. Quiet-to-Active Reawakening

真正的静默期以后出现新的资金/参与者群，而不是持续小量噪声。

这才是 reawakening 应研究的核心，而不是简单换成另一套 flow_burst。

### 11. Graduation / Migration Transition

发行机制前后市场结构变化作为状态转换。

毕业前和毕业后的同一参数不应被默认具有相同含义。

### 12. Liquidity Migration Quality

迁移不是天然 bullish：

研究迁移后 liquidity 是否保持/增加、卖压是否被吸收、有效交易者是否继续。

### 13. Manipulation-Then-Distribution

将明显 manipulation 不简单 hard reject，而建一个特殊短周期实验：

人工冲量出现 → 是否有真实独立需求接棒？

没有则极快退出。

### 14. Creator/Insider Supply Release

研究创建者/早期大户开始释放供应后的市场吸收速度，而非只检查静态 concentration。

### 15. Relative Winner Within Clone Set

同源/同 symbol/同 narrative 同时出现多个 clone 时，不预测整个叙事：

只研究 **同一实时候选集合中的相对 winner**。

必须冻结候选集合，禁止事后选赢家。

### 16. Execution-Survival Alpha

把“价格上涨”与“还能卖掉”拆开。

某币涨 4× 但 sell surface 已严重恶化，应判为低质量机会；一个只涨 50% 但全程保持真实 executable surface 可能更有经济价值。

---

# 8. 我明确反对的策略设计方式

以下做法即使最终统计显示很好，我仍要求强反证：

- `volume 200 / 300 / 400`
- `trades 3 / 5 / 8`
- `buy ratio 0.45 / 0.50 / 0.55`

然后注册成三个新策略。

这属于 **parameter spray**，不是机制多样性。

同样反对：

> 同一个 entry × fast exit / dynamic exit / TP exit / trailing exit
> 然后称四套策略都找到了 alpha。

这首先是一项 **exit experiment**。

---

# 9. 对当前几类历史结果的预裁决

在全历史统计完成前，只做风险分类，不做最终排名。

| 方向 | R1 状态 | 原因 |
|---|---|---|
| Broad launch 高频入口 | **强挑战** | 历史存在大量接近资金耗尽的自然结果；需证明不是把大量 lottery ticket 全买一遍 |
| Dex-visible successor | **强挑战** | 多个历史臂结果高度重复，模板/共同 cohort 风险很高 |
| Flow burst | **保留研究** | 机制合理，但目前大量 reawakening 槽位被其同质化 |
| Reawakening | **重定义后研究** | 不赞成把它简化成 1–6h flow burst |
| Balanced/Peak/Fast exits | **拆成 exit experiment** | 不应分别冒充完整 alpha |
| Wallet evidence | **保留但降权** | 要证明 identity、timeliness、独立贡献 |
| Holder/breadth | **有价值** | 优先动态变化而非静态 snapshot |
| Migration | **有价值** | 应重点研究迁移前后结构转换 |
| Manipulation/risk | **不建议全 hard gate** | 可能同时包含早期收益和极端尾部危险 |
| Relative clone selection | **优先** | 天然有 contemporaneous control，统计设计更干净 |
| Executable-surface survival | **高优先** | 最直接攻击 Paper 漂亮但卖不出的假收益 |

---

# 10. 待最终裁决的核心问题

Codex R2/R3 最终至少需要回答：

1. 全历史有多少策略在 **behavior hash** 意义上真正不同？
2. 去掉重复 cohort 后，历史赢家还剩多少独立事件？
3. 历史最高收益是否集中在旧执行模型/低池深/污染时期？
4. 不同日期/regime 下 strategy ranking 是否发生严重反转？
5. entry 与 exit 到底哪一部分真正贡献收益？
6. 对 matched ordinary/failed tokens，策略假阳性率是多少？
7. 4%/4% 当前 Paper 条件下仍正的机制，在 execution-stress 后是否还能正？
8. 哪些策略收益依赖 stale/incomplete market state？
9. 哪些 wallet/holder/flow 特征在决定时实际上不可得？
10. 目前 206 策略实际需要缩成多少 **独立机制家族**？
11. 新 10–20 个方案是否增加新的经济假设，而非新阈值？
12. 是否至少保留一个高 recall arm，避免所有优化最后变成“什么都不买”？

---

### 实际读取路径

- `E:\memeTrader\docs\PROJECT_CONTEXT\RESEARCH_2026-09-07\REVIEW_SCOPE.md`
- `E:\memeTrader\AGENTS.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\CURRENT_OBJECTIVE_AND_PLAN.md`（当前权威及相关历史段）
- `E:\memeTrader\docs\PROJECT_CONTEXT\STRATEGY_V002_EXECUTION_TABLE_2026-09-06.md`（相关部分）

我**没有读取其他 R1 reviewer 结论**，没有读取未完成的 `HISTORICAL_EVIDENCE_MAP.md` / `HISTORICAL_STATISTICS.md` 作为结果，没有跑大规模 SQL，没有修改代码、数据库或 Runtime。

**最终 R1 裁决：`REVISE / BLOCK PROMOTION`。**

阻止的不是继续 Paper 学习，而是阻止当前任何“历史漂亮策略”直接晋级终极策略。下一轮应让冻结后的全历史统计主动尝试**推翻**上述 16 类机制以及历史赢家；最后留下仍无法被反证击穿的少数机制，而不是从 206 个编号中机械挑前十。
