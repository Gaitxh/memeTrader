# R1 DATA_ENGINEERING

Source Chat: 6a9d94c3-d250-83e8-9ef0-24d6498281ea
Retrieved: 2026-09-07 Asia/Shanghai
Actual Chat response; model self-description is not host-verified model metadata.

ACK

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R1-DATA_ENGINEERING-RESULT
REPLY_TO: C2C-20260907-R1-DATA_ENGINEERING
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: DATA_ENGINEERING
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

MODEL_STATUS: GPT-5.6 Sol；用户要求的实际模型/推理档位无法通过项目侧可靠机制验证，因此评审证据中记为 **未核验**，不以模型自述作为证据。

## 1. R1结论

**结论：REVISE / 必须先做数据资格分层，再做全历史策略排名。**

当前项目已经积累了足够多的真实工程纠错证据，不能把全历史 Paper 结果直接视为同一统计总体。至少存在以下几类已确认污染：

1. **版本/资金期/执行合同不可混算**；
2. **NULL/负 liquidity、HTTP 200 空结果、429/timeout/coverage gap 曾被错误推进为缺池或核销语义**；
3. **极薄池上线性价格×数量计算曾产生不可经济实现的 SELL 回款，形成虚假盈利和后续资金依赖**；
4. **旧的金额/quantity、池身份、报价方向、source_buy_trade_id 等语义曾出现实际缺陷**；
5. **同一市场机会被大量策略同时交易，账户 PNL 可以独立，但统计样本并不独立**；
6. **部分工程异常已经有 correction / contamination / VOID / capital credit，但仍有历史 evidence gap，不能认为“历史已经全部修好”**；
7. **同一策略跨不同资金期、不同费用/滑点/流动性门槛的结果不可直接拼接成一个收益曲线。**

因此，在 `HISTORICAL_STATISTICS.md` 完成之前，我不接受“全历史表现最好/最差策略”的最终排名，也不接受把所有亏损归因为工程错误。

---

# 2. 项目事实

以下均来自我本轮实际只读检查的项目文件/源码，不读取其他 R1 reviewer 结论。

### A. 当前权威边界

`REVIEW_SCOPE.md` 明确：

- 当前资金期是 `funding-20260906-v002-final-1000`；
- 当前通常20U单笔；
- 当前默认双侧4%、额外费用0U、原池1000U门槛；
- **历史版本必须读取当时真实设置，禁止把当前4%/1000U倒灌到过去**；
- 核销 SELL intent 不是实际链上成交；
- unknown / 缺值 / 限流不能当池死亡；
- 不能用未来 ATH、未来钱包分布或当前元数据补历史特征；
- `HISTORICAL_EVIDENCE_MAP.md` 与 `HISTORICAL_STATISTICS.md` 仍在生成，本轮不得冒称已经读取完成结果。

这意味着研究数据必须先有 **version × funding-period × activation × execution-contract** 边界。

---

### B. 当前源码已经明确拒绝 NULL / 非有限 / 负 liquidity

当前 `runtime.py` 的 held quote 校验：

- `liquidity is None`
- 非有限值
- `<0`

都会产生：

`quote_liquidity_unavailable`

当前 `store.py` 的入场路径也明确要求：

- liquidity 非 NULL；
- finite；
- `>=0`；
- 再检查配置的 pool floor。

因此，**当前代码语义本身已经证明：过去把 NULL 或负 liquidity 作为可用池证据的行为属于旧工程缺陷，而不是合法策略表现。**

---

### C. 2026-09-07 已确认的 NULL liquidity 缺陷

当前权威状态文件明确记载：

旧行为：

> 主源正价格但 liquidity=NULL 仍计成功、清空补源队列，并以NULL覆盖完整原池报价。

现在改成：

- 主持仓、exact-pool fallback、新池 held fallback 均要求完整、有限、非负 liquidity；
- 不完整响应记失败；
- **保留旧完整帧及原时间**；
- 不能用不完整响应刷新 freshness；
- fallback 继续走 Gecko/Demo；
- 429/backoff 保留。

这是一个实质性 **point-in-time freshness 污染**：旧实现可能把“只有价格、没有有效流动性”的不完整响应当成新的成功市场帧。

因此受影响窗口不能简单依据 recorded_at / last_success_at 判断行情真的新鲜。

---

### D. HTTP200 空池、429、timeout ≠ pool death

`FOUNDATION_HISTORY_REPAIR_2026-09-06.md` 已确认过：

- Dex exact HTTP200 但返回空，只能证明供应商覆盖缺口；
- 429 以前可能在HTTP层原地重试最长约15秒，占用队列；
- 补源乱序可能让旧响应覆盖主路径较新行情；
- network failure 过去没有正确打断 missing episode，可能把两段缺失拼成一个连续缺池窗口；
- Gecko/Dex池标识差异和EVM大小写也曾漏掉合法池。

后续实现已经把：

`MISSING → network failure → later MISSING`

改成重新开始连续缺池计时，而不是沿用旧 `first_missing_at`。

这说明历史中至少存在一类：

**数据供应商没看到池 → 系统把它解释成池持续不存在 → WRITEOFF**

的错误终态。

---

### E. 已确认错误核销，不等于“所有核销都错”

一个明确 BSC 案例中：

- 26笔、25策略、各20U；
- Dex exact 返回200但0 pair；
- 后续 Gecko 找回原池；
- 原实现将coverage gap当成结构性缺池；
- 最终520U被强制写成终局损失；
- 项目后来追加520U capital credit；
- **原始 BUY / WRITEOFF / PNL 没有被伪造修改。**

这是合格的工程污染证据。

但同一报告还明确说：

- 另外57笔 missing WRITEOFF 没有足够的当时原始请求/逐池quota证据；
- 其中一些后来发现池存在，只能列为 suspect；
- **不能据后来有池就假定当时一定可卖，也不能自动赔付。**

所以必须区分：

`CONFIRMED_ENGINEERING_FAILURE`
和
`UNRESOLVED_EVIDENCE_GAP`

不能一刀切。

---

### F. 极薄池线性 SELL 曾制造严重虚假盈利

这是目前最重要的历史污染之一。

项目已经确认存在：

> 同帧原池流动性很低，但使用 price × remaining quantity × 0.96 计算大额SELL回款。

项目给出的明确案例包括：

- 原池约7.56U；
- 却记出约411.47U SELL 回款。

这不是简单“小幅滑点偏差”，而是**经济量级错误**。

后续项目按用户要求整笔作废：

- 573个生命周期；
- 62策略；
- 1155条交易腿；
- 包括170个薄池线性SELL异常；
- 372个低于当时1U门槛却错误入场；
- 31个已有确认采集故障损失补款。

净现金调整约：

`-2971.388866549485U`

大部分是撤回先前虚假盈利。

因此：

**凡处于该旧执行语义污染窗口中的 headline PNL、PF、EV、Sharpe、胜率、最大回撤，必须使用有效生命周期重新计算，不能使用原始trade聚合。**

---

### G. VOID之后出现“后续资金依赖”

撤回虚假盈利后，有三个账户曾出现负现金：

- `-97.5867U`
- `-88.0928U`
- `-18.5266U`

这说明一个工程错误并不仅污染那一笔交易。

错误盈利可能给后续交易提供了本不应该存在的购买力。

因此历史因果污染至少分两层：

1. **直接污染交易**；
2. **downstream capital dependency / 资金路径污染。**

第二类交易即使自己的行情和执行没有工程错误，也不能作为“正常独立策略样本”直接进入资金约束收益统计。

---

### H. PNL NULL 曾被展示层误当0的风险已修

项目历史接口实库检查发现原始：

`realized_pnl_usd = NULL`

当前实现明确：

- 保留 UNKNOWN；
- 不转换成0。

这是正确行为。

研究端也必须保持：

`NULL ≠ 0`

尤其在：

- profit factor；
- expectancy；
- win rate；
- terminal outcome；
- drawdown

计算中不能偷偷 `COALESCE(...,0)`。

---

### I. source_buy_trade_id 的ID语义曾容易误用

项目报告明确指出：

`position.source_buy_trade_id`

在某些旧路径中是来源标识，**并不等于当前 trade.id**。

实际补款时必须重新按：

- version；
- arm；
- cohort；
- token；

定位真实 BUY trade ID。

这是典型的历史 join-key 风险。

因此全历史统计不能默认：

`position.source_buy_trade_id = trades.id`

跨所有版本永久成立。

---

# 3. 时间戳 / Point-in-time 重点风险

我认为本轮全历史研究至少必须同时保留以下时间概念：

- source published_at；
- observed_at；
- ingested_at；
- snapshot observed/recorded time；
- decision time；
- trigger time；
- post-trigger market frame；
- simulated fill time；
- trade recorded_at；
- strategy registration / activation time；
- funding period activation；
- correction / contamination / VOID time。

不能拿一个 `created_at` 代理所有时钟。

特别是已有项目规则：

> 只有 observed_at 和 ingested_at 均不晚于 decision time 的事实才可进入决策。

另外，现在代码对 stale source 已经会将 feature/confirmation 降级为 identity。

因此历史研究必须基于**当时真正决策可见的 snapshot / evidence ID**，不能重新查询当前Token数据后拼回旧决策。

---

# 4. 版本边界：禁止做一个“总平均”

至少需要以下分层：

`funding_period`
×
`strategy definition/version`
×
`activation frontier`
×
`execution settings activation`
×
`known engineering-valid interval`

原因不是形式主义，而是系统实际发生过：

- 不同双边滑点；
- 不同额外费用；
- pool floor 从1 → 1000 → 100 → 1000等历史变化；
- 不同Paper账户模型；
- 不同entry/exit实现；
- 不同source coverage；
- 不同市场数据完整性；
- 不同持仓核销定义；
- 不同资金初始化。

所以“策略X全历史赚了多少”如果跨这些合同相加，经济含义很弱。

更合理的是：

**先按合同层算，再决定哪些合同具有可比性。**

---

# 5. 共享计算与统计独立性

这里需要区分两个问题。

### 账户独立性

项目已有真实案例证明：

- 同一个 cohort；
- 一个 arm 现金不足不会阻断另一个；
- 同一个token，不同arm可以一个退出、另一个继续持有。

这说明当前独立账户机制是实际存在的。

### 市场样本独立性

但是：

**206个策略同时买同一个Token，不等于206个独立自然机会。**

尤其历史系统有大量：

- 行为完全相同的策略别名；
- 同一 cohort；
- 同一token；
- 同一market frame；
- 相同entry；
- 只轻微变化的exit。

因此统计必须至少同时提供两套结果：

1. **strategy-account result**：真实各账户结果；
2. **unique opportunity / behavioral-cluster result**：同一市场机会去重后的经济结果。

否则：

- N会严重膨胀；
- confidence interval假精确；
- PF/胜率容易被复制策略放大；
- 系统总PNL会被同一机会重复计算很多遍。

共享数据计算本身不是污染，**把共享市场机会当独立样本才是污染。**

---

# 6. 我建议的最小必要纠错

不建议再大规模重写历史。

### 必须做

**A. 建统一 research eligibility layer**

每个生命周期至少输出：

- `VALID`
- `CONFIRMED_ENGINEERING_CONTAMINATION`
- `DOWNSTREAM_CAPITAL_CONTAMINATION`
- `UNRESOLVED_EVIDENCE`
- `VOIDED`
- `NOT_COMPARABLE_EXECUTION_CONTRACT`

不要删除原始交易。

---

**B. 冻结 execution-contract ID**

至少包含：

- buy slippage；
- sell slippage；
- extra fee；
- liquidity floor；
- Paper fill semantics；
- funding period；
- strategy version。

没有这些字段时不要自动假定当前值。

---

**C. Point-in-time eligibility**

研究特征只能从：

`entry_snapshot_id / explicit evidence IDs`

以及其 decision time 之前的immutable记录生成。

缺失就记：

`FEATURE_UNAVAILABLE`

而不是重新查询。

---

**D. JOIN audit**

重点检查旧版本：

- position ↔ BUY trade；
- correction ↔ trade；
- credit ↔ BUY；
- position ↔ original pool；
- market mark ↔ pair；
- arm ↔ version；
- version ↔ funding period。

尤其不要假定历史所有时期的主键语义一致。

---

**E. 经济统计分母双轨**

同时生成：

- per-account；
- per-unique-opportunity。

同一token/cohort/entry-frame的大量策略不要增加市场事件样本数。

---

# 7. 研究数据合格范围

### 一级：可以进入经济性主分析

要求同时满足：

- immutable strategy definition；
- funding/version/execution contract明确；
- activation以后自然前向；
- entry snapshot明确；
- 原池身份明确；
- liquidity有效；
- 无 confirmed contamination；
- 无 downstream capital contamination；
- BUY/SELL/WRITEOFF账本关系自洽；
- NULL没有被补0；
- 退出使用当时合同；
- 无future-data/backfill。

---

### 二级：可做机制研究，不进headline profitability

例如：

- 后来发现 source coverage 可能有问题；
- 缺少原始HTTP evidence；
- historical missing writeoff suspect；
- 部分时钟只能大致恢复；
- 资金依赖污染。

这些可以研究“为什么失败”，但不应该参与正式PF/EV排名。

---

### 三级：只能做工程审计

包括：

- 已VOID的573生命周期；
- 已确认低liquidity错误入场；
- 已确认coverage gap误核销；
- 薄池线性虚假SELL；
- 负liquidity错误；
- 明确错误报价方向/池身份；
- 受虚假盈利资助的下游资金路径。

这类数据**不能拿来训练策略阈值**。

---

# 8. 不能支持的结论

本轮证据不足以支持：

- “历史所有亏损都是工程问题”；
- “工程问题修完后所有策略都会盈利”；
- “所有WRITEOFF都是错的”；
- “所有低流动性结果都无效”；
- “当前206策略就是206个独立alpha”；
- “现在代码修好，所以历史数据自动恢复可信”；
- “资本credit等于原交易本来可以卖回同样金额”；
- “当前4%/4%/1000U可直接应用到过去全部版本”。

---

# 9. 待Codex最终裁决的问题

1. **正式历史统计是否只用 lifecycle eligibility，而非按trade逐腿简单过滤？**
   我建议：是。污染通常属于整个position生命周期。

2. **downstream capital dependency 是否进入主策略收益？**
   我建议：不进入资金约束主排名；可另做“unconstrained signal economics”。

3. **57笔 unresolved missing WRITEOFF 如何处理？**
   我建议：不改原账本；主经济排名排除或单独敏感性区间，不自动判工程错。

4. **行为重复策略如何计N？**
   我建议：账户结果保留，但显著性/系统PNL/机会胜率按unique opportunity或behavioral-equivalence cluster计算。

5. **不同execution contract是否允许合并？**
   默认不合并。若需要长期总览，只做分层meta summary，不把当前成本反算旧期。

6. **VOID/credit/correction后的原始历史是否继续保留？**
   必须保留。研究层过滤，不删除原始证据。

---

# 10. 实际读取路径

本轮实际通过 `@笔记本量化MCP-官方隧道` 只读检查：

- `E:\memeTrader\AGENTS.md`
- `E:\memeTrader\.agents\skills\memetrader-forward\SKILL.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\RESEARCH_2026-09-07\REVIEW_SCOPE.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\CURRENT_OBJECTIVE_AND_PLAN.md`
- `E:\memeTrader\docs\PROJECT_CONTEXT\FOUNDATION_HISTORY_REPAIR_2026-09-06.md`
- `E:\memeTrader\src\memetrader\runtime.py`
- `E:\memeTrader\src\memetrader\store.py`

另仅用只读 grep 定位了相关实现/历史记录，没有执行批量SQL、没有修改代码/数据库、没有读取秘密配置，也没有读取其他 R1 reviewer 的结论。

## 11. 外部证据 / 统计发现 / 假设状态

**外部证据：** 本R1未调用外部资料；本角色先聚焦本地数据完整性，避免把外部机制覆盖项目事实。

**统计发现：** 本轮没有运行新的大规模统计。573 VOID、520U错误核销、57 unresolved、403 credits等数字均来自项目已存在的权威报告，不冒充本轮重新计算。

**假设：**
- 部分尚未识别的旧版本可能仍存在join/time/unit问题；
- 资金依赖污染范围可能大于目前已明确的3个负现金账户；
- 历史行为等价策略的真实独立样本数预计显著小于策略账户数。

以上三项必须由正在生成的历史 evidence map / statistics 验证，当前不能写成事实。

**DATA_ENGINEERING R1最终意见：`REVISE`。**
先建立“版本合同 × lifecycle资格 × unique opportunity”三层研究边界，再谈全历史策略优劣。工程缺陷必须隔离，但自然、干净、成本后仍亏损的策略结果也必须原样保留，不能用“系统以前有bug”把坏策略洗掉。
