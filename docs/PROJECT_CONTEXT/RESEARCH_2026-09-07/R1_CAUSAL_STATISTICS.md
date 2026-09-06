# R1 CAUSAL_STATISTICS

Source Chat: 6a9d94b1-0a10-83ee-ad29-cb5abbb949c8
Retrieved: 2026-09-07 Asia/Shanghai
Actual Chat response; model self-description is not host-verified model metadata.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R1-CAUSAL_STATISTICS-RESULT
REPLY_TO: C2C-20260907-R1-CAUSAL_STATISTICS
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: CAUSAL_STATISTICS
BLOCKS_RELEASE: true
MODEL: GPT-5.6 Sol；实际 Chat 模型/推理档位无法由项目侧可靠验证，按要求标记 **未核验**
SENSITIVE_DATA: NONE

## R1 独立结论

**DISPOSITION: REVISE / BLOCK PROMOTION**

现有历史证据足以证明：项目已经发现若干真实的右尾机会和有意义的机制方向，但**不足以证明任何历史策略具有稳定、可推广的 alpha**。当前最大的统计风险不是“样本少”一个问题，而是五类问题叠加：

1. **不同版本执行成本、流动性门槛、退出语义发生过实质变化，不能横向直接合并。**
2. **大量策略账户共享同一个 Token/同一个 cohort/同一行情路径，账户笔数远大于独立市场样本数。**
3. **历史曾存在明确工程污染窗口，工程污染既不能算策略亏损，也不能从数据库删掉后假装从未发生。**
4. **少数大赢家对总 PNL 的支配已经被实际样本证明非常严重。**
5. **当前正在生成的全历史统计尚未完成，因此本 R1 不接受任何基于其“最终数字”的盈利或失败结论。**

因此，R1 建议 Codex 的最终综合裁决中：**禁止按注册策略数、账户交易数、累计 Paper PNL 对策略直接排名或晋级；应先重建“独立 underlying opportunity + versioned execution contract + clean/contaminated exposure”的统计单位。**

---

# 一、项目事实

### 1. 历史成本必须按版本冻结，不能用当前 4%/4% 回算全部历史

`REVIEW_SCOPE.md` 明确规定：

- 当前生产默认买入滑点 4%、卖出滑点 4%、额外手续费 0U、原池门槛 1000U；
- **各历史版本真实设置分别读取，禁止倒灌当前成本**；
- 当前是轻量 Paper，不保证真实可成交；
- WRITEOFF/SELL intent 也不是实际链上成交证明。

这意味着“全历史策略 A 比 B 多赚多少”只有在两者的：

- execution activation；
- buy/sell friction；
- pool floor；
- fill/quote contract；
- exit semantics；

都可比较时才有意义。

否则最合理的统计对象是**版本内结果 + 版本间标准化敏感性分析**，而不是一条跨版本累计收益曲线。

---

### 2. 历史账户不是独立样本

我实际读取的历史 universe 文件记录：

- 13 个真实版本；
- 156 个历史 strategy instance；
- 36 个 unique arm IDs；
- 124 个 behavior-contract families；
- 当时 `paper_candidate_count = 0`；
- 明确写明：**shared-cohort projected accounts are paired observations**；
- exit 比较必须使用双方共同参与的 cohort 交集。

这和后续项目事实一致：同一个 underlying market opportunity 可以被复制到多个策略账户。因此：

> `206 个账户 × 若干交易` ≠ `206 个独立实验`

主要统计单位至少应下降到：

**token × canonical pool/surface × entry opportunity/cohort × 时间块**

然后策略只是这个共同机会上的不同 treatment。

同一个 Token 同时被 20 个策略买入，不能在显著性、胜率、bootstrap 或有效 N 中算 20 次。

---

### 3. Winner dependence 已经不是理论风险，而是实证事实

旧 v3 已留下非常强的反例：

- dynamic：13 个 terminal，合计约 **+164.97U**
- 单一最大赢家约 **+573.26U**
- 删除它之后约 **-408.29U**
- fixed：22 个 terminal 合计约 **+20.50U**
- 删除最大赢家后约 **-78.87U**

另外 v4 早期动态结果同样由 cohort 2179 的约 +78.32U 显著驱动。

所以目前任何仅报告：

- 累计 PNL；
- 平均收益；
- 胜率；

而不报告 Top1/Top3 concentration 与 remove-best robustness 的结果，都可能非常误导。

需要特别澄清用户提到的“删掉最大1/3笔”：

**项目已有正式要求是 `remove-best-1` 和 `remove-best-3`，不是把收益最高的三分之一交易永久从样本删除。**

“删除最大一笔/三笔”应是**敏感性分析**，原始 ITT 分母一笔都不能删。如果额外测试“去掉顶部 1/3 outcome”，也只能作为 stress test，不能成为主估计量，否则反而会人为删除 Meme 策略最重要的右尾经济结构。

---

### 4. 工程污染必须隔离，但不能选择性删除亏损

当前权威计划已经确认至少包括：

- 负 liquidity 错误导致的污染 BUY；
- SQLite 锁顺序造成的停滞窗口；
- NULL liquidity 曾错误刷新为成功；
- 历史 pool/quote/cross-pool 等问题；
- 若干历史 missing/writeoff 证据不足；
- 老账期中的污染记录继续保留，不重写历史。

因此策略损失应至少拆成：

**A. clean economic outcome**
规则和输入在当时合同下可因果解释。

**B. engineering-contaminated outcome**
明确存在会改变交易发生/成交/退出/PNL 的工程故障。

**C. unresolved evidence**
无法证明自然亏损，也无法证明工程损失。

C 类绝不能强行归 A 或 B。

同理，工程修复后的漂亮结果也不能自动证明经济策略优越。

---

# 二、统计发现

### 1. 当前最严重的伪样本量来自“策略账户复制”

对同一个 Token：

- 不同 entry filter；
- 不同 exit；
- 不同 sizing；

如果共享一个原始 opportunity，属于**相关 treatment outcomes**。

推荐主分母：

`unique opportunity_id`

最小键建议由 Codex 根据现有真实 schema 映射，但统计语义应接近：

`chain + canonical original pool/surface + token + frozen entry-opportunity/cohort`

需要另外记录：

`strategy/version/treatment`

这样可以形成：

- 同机会成对比较；
- strategy-vs-baseline paired delta；
- cluster bootstrap；
- opportunity-level portfolio PNL。

而不是把复制账户当独立 Bernoulli 样本。

---

### 2. 多重选择偏差现在非常高

历史上已经存在：

- 多版本；
- 多策略；
- 122 个 V002；
- 大量相近机制；
- 不同门控；
- 不同退出；
- 不同时间窗。

如果从这些策略中选择历史 PNL 最好的 10–20 个直接部署，会形成典型的：

**multiple testing / garden-of-forking-paths / winner's curse**

所以“终极策略”的来源不能是：

> 在全历史中排名前 10。

而应是：

> 全历史用于提出假设 → 去重成机制家族 → 冻结新规则 → 新 frontier 后严格前向比较。

历史只能决定**哪些假设值得继续赌**，不能证明未来 alpha。

---

### 3. 既有成熟门只能当最低检查点，不能当统计显著性证明

历史资料里曾有一个旧 universe 分类门：

- terminal cohorts ≥30；
- total >0；
- median >0；
- 10% trimmed mean >0；
- ≥50% positive time blocks；
- best-win concentration ≤75%；
- 无工程/因果 invalidation。

更严格的后续项目规范还出现过：

- ≥100 closed；
- ≥15 dates；
- ≥20 losses；
- ≥10 dead/no-route terminal cases；
- remove-best/date-block robustness。

我的判断是：

**不要把任何一个 N=30 或 N=100 门槛解释成“统计显著”。**

它们只能是预注册的“可以开始比较/可以开始资本复审”的 operational maturity gate。

Meme 收益重尾、时间非平稳、同币相关、退出删失都使普通 IID t-test 非常脆弱。

---

# 三、四类 Token 的可实际执行对照设计

关键原则：

**分类标签允许使用未来结果；特征不允许。**

也就是说可以在研究完成后说某币属于“暴涨/暴跌”，但策略输入只能取 entry 时已经存在的信息。

## A. 暴涨币

事后标签建议不要只用 ATH。

主标签应使用固定 horizon 的、同一原池/同一 surface：

- `H=15m / 60m / 240m`
- 可观察价格 return；
- 同时要求 liquidity/sellability 状态；
- 若已有 amount-specific executable outcome，则单列更高质量标签。

例如研究标签：

`large_up_60m`

必须在研究开始前冻结阈值，不根据赢家分布临时挑阈值。

### 事前特征

只使用 entry 时间前已有：

- token/pool age；
- liquidity；
- 5m volume；
- buy/sell count；
- buy/sell imbalance；
- turnover；
- 价格短周期加速度；
- 连续上涨/回撤路径；
- participant breadth；
- buyer concentration；
- wallet/funding breadth，前提是当时已有；
- pool lifecycle / migration 状态；
- launchpad/venue；
- 当前可得 sellability/route；
- creation/holder 信息只在真实 point-in-time 有覆盖时使用。

---

## B. 普通币

不要定义为“既不是暴涨也不是暴跌的剩下垃圾桶”。

最好预注册一个明确中间区间，例如：

- 60m executable/market outcome 落在预先固定中央区间；
- 且没有 dead/no-route terminal。

普通币是最重要的 control，因为它能回答：

> 某个特征是在识别右尾，还是只是在识别“活着的币”。

---

## C. 失败币

失败不能简单等于“没涨”。

应区分：

- 没达到策略门；
- 没有 route；
- liquidity collapse；
- 数据缺失；
- quote stale；
- 已买后经济亏损；
- 根本没有产生可执行 entry；
- 工程污染。

否则会把 discovery/data failure 和 economic failure 混成同一个 negative class。

对于 entry-feature 学习，主对照应优先是：

**当时同样 decision-eligible、同样拥有完整特征、但后来没有暴涨的 Token。**

而不是所有发现过的 Token。

---

## D. 暴跌 / dead / rug 类

必须拆分 competing risks：

- price collapse；
- liquidity removal；
- sell drain；
- no-route；
- pool migration；
- data loss/coverage failure；
- writeoff terminal。

“后来跌了 90%”不能在买入前成为 `rug=true` 特征。

正确方法：

在 entry time 冻结 risk indicators，然后终局成熟后比较：

- time-to-warning；
- time-to-dead；
- 是否曾有经济退出窗口；
- conservative recoverable PNL；
- writeoff probability；
- worst-tail outcome。

这比简单二分类“rug/not rug”更适合当前系统。

---

# 四、推荐的核心因果数据结构

每一个自然机会形成一条 immutable entry row：

`opportunity_id`

包含：

- `decision_time`
- `strategy_registration_frontier`
- `execution_activation_id`
- `strategy_version`
- `token`
- `canonical_pool/surface`
- `chain`
- 所有 point-in-time feature values
- 每个 feature 的 `observed_at/ingested_at`
- missingness
- eligibility
- rejection reason
- engineering contamination state

之后 outcome 单独 append：

- 15m
- 60m
- 240m
- terminal/dead
- realized Paper
- writeoff/no-route
- executable valuation coverage

绝不能用 outcome 更新当时 feature row。

---

# 五、建议的比较方式

对于每一个候选机制，应同时报告：

- unique opportunity N；
- terminal N；
- unresolved/right-censored N；
- 日期数；
- chain/venue；
- clean / contaminated / unresolved；
- total net PNL；
- median；
- 10% trimmed mean；
- hit rate；
- worst loss / lower-tail；
- writeoff/no-route；
- Top1/Top3 contribution；
- remove-best-1；
- remove-best-3；
- 按日期 block 的结果；
- 同一 Token/机会上的 paired baseline delta；
- capital-time efficiency。

**不要先给 p-value。**

当前阶段首先应确定 estimand、cluster、删失和合同可比性。否则显著性数字只会产生虚假的精确感。

---

# 六、10–20 个候选策略筛选时的统计约束

不反对最后留下 10–20 个机制，但要求它们是**机制多样性**，而不是阈值网格。

不应该出现：

- momentum >80；
- momentum >82；
- momentum >85；
- momentum >87；

然后说有四个策略。

更合理的多样性轴是：

1. acceleration；
2. flow imbalance；
3. breadth；
4. concentration；
5. liquidity survival；
6. participant-quality/funding breadth；
7. post-impulse reset/reawakening；
8. volatility-normalized momentum；
9. migration/absorption；
10. launch lifecycle；
11. manipulation/periodicity；
12. creator/issuer behavior；
13. dynamic peak/trailing exit；
14. capital-release/fast-loss exit；
15. route/sellability risk；
16. regime/time-of-day conditional treatment。

每个机制最多保留少量明确 comparator，避免再次制造 100+ correlated arms 后从中挑赢家。

---

# 七、建议的严格前向可证伪条件

对任何新候选，在 deployment frontier 前冻结：

**Primary estimand**

`candidate policy − predefined baseline` 的 unique-opportunity、成本后经济差。

**最低研究比较 checkpoint**

可以沿用项目既有思想：

- ≥30 terminal unique opportunities；
- ≥15 independent dates；
- ≥5 positive + ≥5 nonpositive；

但只表示“可以研究比较”。

**继续/晋级要求**

至少：

- median 不依赖单赢家；
- remove-best-1/3 不发生灾难性翻转，或者翻转程度在预注册容忍范围内；
- 多日期 block 不是只靠一天；
- no-route/writeoff 包含在 ITT；
- execution coverage 足够；
- 没有重大工程污染；
- paired baseline delta 不只是 copied-account PNL。

**提前否证**

不必机械等到 N=100。如果出现：

- catastrophic writeoff；
- 连续多个日期明显 dominated；
- clean sample 下 median、trimmed mean 和 tail 同时恶化；
- strategy 只靠极端单赢家；
- 规则实际没有行为差异；

可以提前停止。

---

# 八、我当前不接受的结论

以下在 R1 阶段均应判为 **NOT ESTABLISHED**：

- “122 个 V002 已证明比旧策略更优。”
- “Paper 累积总 PNL 为正，所以存在稳定 alpha。”
- “某策略交易数多，因此证据更强。”
- “同一个币被几十个策略盈利，是几十个成功样本。”
- “工程修复后历史亏损都应删掉。”
- “后来暴涨币当前钱包/持有人结构可用于解释当时为什么应该买。”
- “删掉最大赢家以后为正，就证明稳健。”
- “N≥30 就具有统计显著性。”
- “全历史统计已经完成。”

最后一点尤其明确：`REVIEW_SCOPE.md` 将 `HISTORICAL_EVIDENCE_MAP.md` 与 `HISTORICAL_STATISTICS.md` 标记为**生成中**。本 R1 没有把它们作为已完成统计结论使用。

---

# 九、外部证据

**R1 未独立开展外部互联网证据研究。**

这是有意遵守本轮角色边界：外部实证由独立 `EXTERNAL_RESEARCH` reviewer 负责，R1 不先读其他 reviewer 结论。

本结果中涉及因果统计的方法判断属于本 reviewer 的统计设计意见，不伪装为项目已有实证结果。

---

# 十、实际读取路径

本轮实际通过 `@笔记本量化MCP-官方隧道` 只读访问：

- `E:\memeTrader\AGENTS.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\RESEARCH_2026-09-07\REVIEW_SCOPE.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\CURRENT_OBJECTIVE_AND_PLAN.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\CHATGPT_ONCHAIN_FIRST_STRATEGIC_CONVERGENCE_2026-09-03.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\CHATGPT_EXECUTION_ECONOMICS_AND_RUG_ESCAPE_SPEC_2026-09-04.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\CHAIN_MEME_TRADER_HISTORICAL_STRATEGY_UNIVERSE_2026-09-04.json`

并对 `docs/PROJECT_CONTEXT` 做了**有界关键词检索**，定位：

- winner-removal；
- maturity gate；
- paired/shared cohort；
- contamination；
- survivor bias；
- remove-best；
- clustering；

没有运行大量 SQL，没有修改代码、数据库或 Runtime，也没有访问 secret/config 敏感值。

---

# 十一、交给 Codex/R2-R3 的待裁决问题

1. **全历史主统计单位最终采用什么？**
   我建议 unique underlying opportunity 为主，strategy account 为 treatment outcome。

2. **跨版本收益是否完全禁止 pooled estimate？**
   我的建议：主报告禁止；只有在显式重建相同 execution contract 后允许敏感性标准化。

3. **工程污染样本如何处理？**
   建议保留原始 ITT ledger，同时从 clean economic estimand 排除，并单独列 contaminated denominator；不得物理删除。

4. **unresolved/missing/no-route 如何进入结果？**
   必须按冻结合同分别处理，不能统一补 0，也不能统一删除。

5. **最终 10–20 个候选如何防多重选择？**
   必须按机制家族去重；历史数据只用于 hypothesis generation，新 frontier 才用于 confirmatory comparison。

6. **“暴涨/普通/失败/暴跌”阈值何时冻结？**
   必须在看到本轮正式对照结果前冻结，否则标签本身也存在后验选择。

7. **是否接受“去掉最大 1/3 outcome”的 robustness？**
   可作为附加 stress test；**不可替代全样本 ITT、remove-best-1/3 和 trimmed mean，更不能删库。**

8. **历史 30-terminal gate 是否继续有效？**
   可作为 early research checkpoint；不能作为盈利证明或资本放大门。

**R1 总结：当前正确方向不是继续寻找“历史收益最高的策略”，而是先把“一个真实市场机会到底算几次、它当时处于哪个执行合同、结果有没有被工程污染、是不是靠一两个超级赢家”解决清楚。做完这一步，10–20 个候选的前向实验才具有可证伪性。**
