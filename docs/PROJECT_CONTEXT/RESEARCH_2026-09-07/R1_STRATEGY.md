# R1 STRATEGY

Source Chat: 6a9d94a3-6898-83e9-b5ce-9c598543fabf
Retrieved: 2026-09-07 Asia/Shanghai
Actual Chat response; model self-description is not host-verified model metadata.

ACK

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R1-STRATEGY-RESULT
REPLY_TO: C2C-20260907-R1-STRATEGY
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: STRATEGY_HISTORY
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

本轮已实际通过 **笔记本量化MCP-官方隧道** 只读打开 `E:\memeTrader`。未修改文件、代码、数据库、Runtime；未运行大量 SQL；**未阅读其他 R1 reviewer 结论**。当前会话模型可识别为 **GPT-5.6 Sol**；具体后台 thinking/reasoning effort 档位没有可靠运行元数据暴露给我，因此不冒称 xhigh/GPT-6。

## 1. 实际读取的主要路径

本轮实际读取：

- `E:\memeTrader\AGENTS.md`
- `E:\memeTrader\.agents\skills\memetrader-forward\SKILL.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/REVIEW_SCOPE.md`
- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md`
- `docs/PROJECT_CONTEXT/STRATEGY_VERSION_REVIEW_2026-09-06.md`
- `docs/PROJECT_CONTEXT/CHATGPT_HISTORICAL_HANDOFF_RESEARCH_RECONCILIATION_2026-09-04.md`
- `docs/PROJECT_CONTEXT/NINE_DIRECTION_IMPLEMENTATION_2026-09-05.md`
- `docs/PROJECT_CONTEXT/L0_OUTCOMES_RELEASE_2026-09-06.md`
- `docs/PROJECT_CONTEXT/BROAD_COST_COVERAGE_SCALEOUT_RESEARCH_2026-09-05.md`
- `docs/PROJECT_CONTEXT/NEXT_STRATEGY_PROPOSAL_2026-09-06.md`
- `docs/PROJECT_CONTEXT/CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json`，实际读取其总览、方法学、executive summary及首批实例定义；该文件约4.6万行，本轮没有假装逐行通读。

另外实际列举了 `docs/PROJECT_CONTEXT/` 目录，以定位历史策略/版本/结果/工程污染相关材料。

**没有读取正在生成的**：

- `RESEARCH_2026-09-07/HISTORICAL_EVIDENCE_MAP.md`
- `RESEARCH_2026-09-07/HISTORICAL_STATISTICS.md`
- `RESEARCH_2026-09-07/EXTERNAL_EMPIRICAL_EVIDENCE.md`

所以以下判断**不引用、也不预判它们的结果**。

---

# 2. 最重要的历史事实判断

### A. “当前206策略”绝不能代表项目策略历史

`REVIEW_SCOPE.md` 本身已经规定206只是当前定位快照。

更早的 `CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json` 已经存在：

- 13个历史版本；
- 156个版本×策略实例；
- 36个 unique arm ID；
- 124个 behavior-contract family；
- 当时分类：
  - 71 `SUPERSEDED_REUSABLE`
  - 14 `RETIRED_ECONOMIC_FAILURE`
  - 36 `RETIRED_ENGINEERING_FAILURE`
  - 24 `INVALID_OR_UNCOMPARABLE`
  - 11 `SHADOW_CANDIDATE`
- 当时 **Paper candidate = 0**。

之后又继续加入了九方向、L0、cycle、wallet/event、pregrad、migration、Broad、V002 等大量机制，因此这次重评必须以**真实交易行为合同**作为归并单位，而不是按206个显示编号逐个评价。

这是本轮我认为最重要的治理原则。

---

# 3. 可复用的“成功机制”

这里的“成功”主要指**机制/实验设计成功**，不是长期盈利成功。

### 3.1 严格前向 + immutable frontier

这是历史上最稳定、最值得保留的东西。

已经反复形成：

`signal → frozen state → independent later observation → BUY/SELL`

而不是：

`历史赢家 → 找特征 → 回填过去`

这套结构适用于：

- reawakening；
- quiet→breakout；
- pullback→reclaim；
- migration；
- wallet participation；
- official event；
- clone episode；
- L0 continuation；
- profit lock；
- regime。

**建议以后10–20个终极候选全部继承这个结构，不再产生另一套实验框架。**

### 3.2 “状态转换”比单一绝对阈值更值得继续研究

已有机制中最有研究价值的共同部分不是某个12%、30%、50笔，而是：

- 静默 → 复苏；
- 冲击 → 回撤 → 收复；
- 价格上涨 + 流动性保持；
- 首波失败 → 二次恢复；
- migration前后状态切换；
- 盈利 → 动能衰退；
- 入场后承接失败；
- 老币沉寂 → 新资本episode。

也就是说，**transition / sequence** 比单帧“涨了多少、交易数多少”更有可能形成行为上真正不同的策略。

### 3.3 入场和退出应拆开研究

历史里已经出现非常清楚的证据：

`broad_cost_coverage_scaleout_v1` 的设计动机来自：

- 1865个清洁终局；
- 199个运行中曾达到+12%；
- 其中109个最终实现PNL转负；
- 155个曾达到+30%。

这并不能证明该scaleout一定盈利，但至少证明一个重要机制：

> **“找到赢家”和“把赢家兑现成扣成本利润”是两个独立问题。**

因此未来不应把所有研究预算继续花在越来越复杂的entry gate。

### 3.4 L0廉价特征值得保留为主干

现在系统真正能稳定、大规模、低成本取得的仍主要是：

- price；
- liquidity；
- volume；
- tx count；
- buy/sell结构；
- age；
- 多时间窗；
- 同池连续帧。

L0实验可以：

- 不新增RPC；
- 不阻塞退出；
- 严格前向；
- 大覆盖；
- 做候选/对照。

这比设计十个依赖完整钱包图、实时KOL或复杂逐笔流的策略更符合当前资源现实。

---

# 4. 明确的失败机制

### 4.1 单帧追涨 / 单条件momentum很危险

历史Broad类已经提供了很强的警告。

例如策略126旧结果中：

- 321 BUY；
- 188次硬止损贡献约 `-2216U`；
- 41次高档止盈贡献约 `+1489U`。

说明这个家族不是“完全没有右尾”，恰恰相反：

> **确实能抓到右尾，但大量false breakout把右尾利润吃掉。**

所以正确问题不是简单“把门槛再调严”。

需要研究的是：

- breakout continuation；
- economic-size confirmation；
- participation breadth；
- post-entry continuation failure；
- episode structure。

### 4.2 “活着”不等于“持续”

策略127是很典型的反例。

它用：

> 5–15分钟池龄 + prior55 transactions >2

作为成熟延续条件。

已有结果里：

- 胜率约7.1%；
- 156次max-hold仍合计亏损；
- 50次hard stop亏损。

这表明：

> 历史存在几笔交易 ≠ 当前有持续需求。

未来类似“存在性指标”不应该再作为独立策略核心。

### 4.3 完全零活跃才退出过于迟钝

策略083：

- 79个有效生命周期；
- 41个最后核销；
- 核销约 `-820U`；
- 5m zero-activity退出29次也亏损。

所以：

> 等到成交量和成交数都完全归零，往往已经太晚。

更好的可证伪机制应当是连续恶化：

`price↓ + liquidity non-increasing + recovery<cost`

而非必须等到0。

### 4.4 Conditional runner目前没有支持“多拿一会儿更好”

九方向的同cohort paired结果非常值得保留：

41组双方都终结时：

- candidate：`-187.40U`
- control：`-171.44U`
- PF：0.198 vs 0.205
- positive：19.5% vs 26.8%

而且去最好1/3笔后candidate仍更差。

这不是充分证据宣布runner永远失败，但已经构成很好的**反证**：

> “短期还有买压，所以利润仓应该继续拿”不能当默认正确。

这支持profit-lock / continuation-failure方向，而不是更宽松runner。

---

# 5. 不能拿来评价策略的历史

这个问题非常严重。

历史文件明确出现过：

- v6 negative cash；
- v7 scheduler interference；
- v8错误terminal semantics；
- v9单次no-route直接writeoff；
- v10最弱账户共享cash veto；
- v11持续Jupiter valuation覆盖问题；
- v12 Jupiter BUY依赖；
- dust liquidity BUY；
- 低流动性线性成交；
- 573生命周期VOID；
- 371笔存在历史capital dependency；
- NULL liquidity覆盖完整frame；
- 持仓原池覆盖/陈旧；
- BSC负liquidity；
- SQLite锁序导致全停；
- duplicate frame清空pending signal；
- 原池identity/quote方向错误；
- 不同pool substitution问题。

因此：

> **凡是某策略主要交易发生于这些污染窗，亏损不能直接归咎策略；盈利更不能作为alpha证据。**

这是本轮历史重评必须严格执行的隔离规则。

---

# 6. 证据明显不足的方向

以下方向我不建议现在宣布成功或失败：

- wallet confirmation；
- smart-wallet distribution；
- creator/issuance holder；
- official-event actual flow；
- migration flow；
- KOL-lite；
- narrative/info-first；
- quiet reawakening；
- clone leadership；
- regime；
- mature reawakening；
- PREGRAD；
- common funding breadth。

原因主要不是“规则不好”，而是：

1. 自然事件少；
2. 输入覆盖尚不足；
3. 有的刚部署；
4. 钱包“地址”并不等于独立人；
5. amountful flow并非全覆盖；
6. 某些链只实现部分协议；
7. current first-observed不等于完整发行状态。

**零交易不能作为否决理由。**

---

# 7. 我建议优先进入最终候选池的行为方向

不是让Codex现在实施，只是R1的独立候选。

我更倾向保留 **10–14个真正行为不同的机制**，而不是20个阈值变体。

### 第一组：Breakout真假辨识

1. **持续突破**
   - 多独立帧持续，而非single spike。

2. **经济成交额确认突破**
   - tx count与实际经济volume联合，避免大量微额交易假热度。

3. **参与扩散突破**
   - 新参与地址扩散，而不是同一批地址重复交易。
   - 只在输入覆盖够的链运行。

### 第二组：反转/再启动

4. **冲击→回撤→收复**
   - 和直接追涨control保持严格对照。

5. **流动性保持的恐慌反转**
   - price reclaim同时要求pool没有同步塌缩。

6. **首波失败→重新加速**
   - 第一wave结束后建立新episode，不靠一直扛仓等待第二波。

7. **成熟币新资本episode**
   - old token重新活跃作为全新cohort。

### 第三组：退出机制

8. **Post-entry continuation failure**
   - 买入60/120秒后仍未形成承接则退出。

9. **Profit lock**
   - 本金实际回收后，连续恶化退出余仓。

10. **Peak/drawdown single-wave exit**
   - 运行高点后的持续回撤，而不是静态TP。

### 第四组：结构性市场选择

11. **Clone episode leader**
   - 同链同symbol冻结候选集，比较liquidity leader与volume leader。

12. **Leader handoff**
   - 第一leader衰退、既存第二候选接棒；episode最多一次切换。

13. **Observed-set relative strength**
   - 同chain/lifecycle整体弱时仍保持price+liq的目标。

### 第五组：高质量稀疏证据

14. **Event/Wallet confirmation**
   - 作为单独小额实验，而不是给所有策略加 universal gate。

这14个已经足够形成机制多样性。

---

# 8. 我明确反对的扩展方式

### 不要继续靠“更严门控”生产策略

例如：

- 50笔改70笔；
- volume 200改300；
- age 120改90；
- liquidity再乘一个门槛；
- 再增加3个AND条件。

这类东西可能减少亏损，也可能只是减少交易，**行为机制没有真正改变**。

### 不要把entry × exit笛卡尔积注册成几十个“策略”

例如：

5种entry × 5种exit = 25个策略，

统计上高度相关，经济上也不是真正25种独立思想。

应先分别证明：

- entry有没有增量；
- exit有没有增量；

然后才组合。

### 不要把共享同币账户当独立样本

历史报告已经明确：

> shared-cohort projected accounts = paired observations。

未来所有“十大/二十大最终策略”都应同时报告：

- account级；
- token/cohort级；
- episode级。

否则账户数量越多，虚假的样本量越漂亮。

---

# 9. 对历史“漂亮结果”的反证要求

若后续 `HISTORICAL_STATISTICS.md` 出现非常漂亮的策略，我建议至少过以下反证：

1. 同一token/cohort去重后仍好吗？
2. 同一版本时代、相同费用合同下仍好吗？
3. 去最大赢家1笔后如何？
4. 去最大3笔后如何？
5. median是否>0？
6. trimmed mean是否>0？
7. 多时间块是否多数为正？
8. 结果是否集中于某一天/某链？
9. 是否来自工程污染窗口？
10. writeoff语义是否当时正确？
11. 是否在资金耗尽前已经恶化？
12. 能否找到同期未上涨/暴跌对照？

若只有total PNL好、其它全差，我不会支持晋级。

---

# 10. 待本轮综合裁决的问题

我建议R2/R3重点裁决：

**Q1. Broad类究竟应继续保留一个“高召回基线”，还是退出正式Paper只作为control？**
当前其右尾是真实存在的，但false breakout成本同样巨大。

**Q2. 下一阶段资源应该更多给entry还是exit？**
我偏向 **exit与post-entry state占至少一半研究预算**，因为历史已经显示“曾经盈利→最终亏损”规模不可忽略。

**Q3. 是否将“single-wave / new-episode”提升为系统一级状态机？**
我倾向赞成。这样第二波不再靠延长第一笔持仓来捕获，而作为新cohort处理。

**Q4. 钱包/事件/KOL是交易主干还是稀疏增强？**
在当前免费资源和覆盖下，我支持**稀疏独立实验**，不支持变成所有策略的硬前置门。

**Q5. 当前V002 122个修订中有多少实际上只是同族微调？**
需要等待正在生成的全历史统计/行为合同归并后再判，我本轮不猜。

---

# R1结论

**DISPOSITION: CONTINUE / NO PROMOTION CLAIM**

目前历史材料支持的最强结论不是“已经找到终极盈利策略”，而是：

> 项目已经积累出了相当多真正不同的可证伪机制，但历史策略数量明显大于独立经济思想数量；漂亮/糟糕结果同时受到共享cohort、费用时代、资金约束和工程污染影响。下一步应把策略压缩成少数机制家族，在严格相同时代和同期cohort下比较，并把更多研究从“入场再加门”转向“状态转换 + 买后承接 + 利润兑现 + 新episode”。

我目前认为最值得保留的主线是：

**持续突破 / 参与扩散 / reclaim / liquidity-preserving reversal / reawakening / clone leadership / relative strength / continuation-failure / profit-lock / peak-drawdown exit**。

其中任何一个目前都**不能称已证明长期盈利**。统计文件仍在生成，本R1不杜撰其内容。Codex仍应保持唯一 writer。
