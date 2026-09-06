# R2 EXTERNAL_RESEARCH

Source Chat: 6a9d94ca-7b7c-83ee-885b-1cad2a17c7c6
Actual response; model setting not independently verified. Markdown trailing whitespace normalized.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R2-EXTERNAL_RESEARCH-RESULT
REPLY_TO: C2C-20260907-R2-EXTERNAL_RESEARCH
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: EXTERNAL_RESEARCH
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

## 1. R2 disposition

**DISPOSITION: REVISE / ALLOW_BOUNDED_SMALL_PAPER / BLOCK_ALPHA_PROMOTION**

R2 已实际交叉读取完成后的共同证据，并阅读了至少两份与本角色存在张力的 R1。我的结论比 R1 更收敛：

**当前证据足以删并重复机制、冻结一批可证伪的小额 Paper 候选，但不足以宣布任何 alpha，更不足以从历史 PNL 排行榜选“终极策略”。**

“BLOCK PROMOTION”和“BLOCK PAPER EXPERIMENT”必须严格分开。

- **阻止盈利/alpha 宣称：强阻止。**
- **阻止新候选小额严格前向 Paper：不阻止，只要满足下述资源和时序条件。**
- Live：不具资格。
- 不重置账户。
- 不关闭历史策略。
- 不改写旧历史。
- 本轮不依赖仍在进行中的 `TOKEN_PRECURSOR_EVIDENCE.md` 得出任何正面结论。

---

# 2. 实际读取材料

本轮实际只读：

- `E:\memeTrader\AGENTS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R2_DESIGN_QUESTIONS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/HISTORICAL_EVIDENCE_MAP.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/HISTORICAL_STATISTICS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/EXTERNAL_EMPIRICAL_EVIDENCE.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_CAUSAL_STATISTICS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_ADVERSARIAL_RISK.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_MICROSTRUCTURE.md`

没有运行 SQL，没有写文件、代码、DB 或 Runtime。

模型/推理档位作为项目审计元数据：**UNVERIFIED**。

---

# 3. 先纠正 R1 外部研究中的 BONK 日期错误

我在 R1 中曾把 BONK 写成 **2022-12-08**，该日期现在撤回。

重新直接核验原始/一手程度更高的来源：

- BONK 官方 About 页称其由 Solana builders 在 **Christmas Day** launch；
- CoinGecko 的原始研究明确写 **launch on December 25, 2022**；
- CoinGecko 同文还区分了 **2022-12-10 首次宣布 airdrop** 与 **2022-12-25 launch**。citeturn950272search1turn467808search0

因此 R2 统一采用：

**BONK launch = 2022-12-25。**
**airdrop announcement = 2022-12-10。**

[BONK 官方 About](https://www.bonkcoin.com/about?utm_source=chatgpt.com)
[CoinGecko BONK 原始研究](https://www.coingecko.com/research/publications/bonk-shiba-doge-growth?utm_source=chatgpt.com)

这也恰好说明本轮时序纪律为什么重要：**announcement、launch、first trade、local first-seen 是四个不同时间，不能混成一个 t0。**

---

# 4. 完成后的历史统计改变了哪些判断

现在可以引用已经完成的统计，而不是 R1 时的猜测。

### 4.1 历史“漂亮结果”确实经不起 token 聚类

最严重的是 v22：

- 闭环 PNL：**+7,316,782.49U**
- 闭环中位数：**-1.54U**
- 只有 **5.27%** 闭环为正
- 10% trimmed mean：**-3.25U**
- 单一 token 占正 token PNL：**94.14%**
- 前三 token：**98.16%**
- 移除最佳 token 后：**-232,664.38U**
- 移除前三 token 后：**-554,671.51U**

所以 v22 巨额盈利不是“稳定策略群胜利”，而是一个极端右尾 token 被多个账户/episode 投影出来的典型案例。

这强烈确认因果 R1 和风险 R1 对 **winner dependence** 的担忧。

---

### 4.2 当前最终资金期不能用于 alpha 排名

`funding-20260906-v002-final-1000` 截止统计时只有：

**1.28936 小时。**

虽然已经有：

- 8,413 BUY
- 6,681 完整闭环
- 341 个闭环 token
- 闭环 PNL **-40,134.18U**
- PF **0.231**
- 胜率 **17.00%**
- expectancy **-6.01U**
- 中位数 **-4.16U**

这些数字很差，但账户成交量不能替代：

- 独立 token/episode 数；
- 成熟时间；
- 多日期；
- 工程修复后的稳定区间；
- 同机会 treatment comparison。

所以：

> **这些数字足以阻止“V002 已优化成功”的说法，却还不足以判决所有机制经济死亡。**

---

### 4.3 当前唯一账面正的 arm 也没有晋级意义

`watched_wallet_confirmed_entry_control_v1`：

- 39 closed / 39 token
- +4.83U
- PF 1.10
- 中位数 -0.264U
- 移除最佳三笔后 **-29.61U**

而且它还是 **control**。

这正面反驳“钱包信息已经产生 alpha”的叙事。

---

### 4.4 当前真正值得看的有限机制线索

配对结果：

- `l0_continuation_failure`：91 个共同闭仓 opportunity，candidate 相对 control **+21.79U**
- 但两边总体仍分别约 **-642.68/-648.07U**
- `l0_profit_lock`：59 个交集，candidate **-62.54U**
- `conditional_runner`：108 个交集，candidate **-84.84U**

所以目前最合理的解释是：

**快速淘汰可能有“少亏”信号；锁利和延长持有当前没有正面证据。**

仍然不是 alpha。

---

# 5. 对其他 R1 的明确反驳/限定

## A. 对 CAUSAL_STATISTICS R1 的限定

我同意它关于 unique-opportunity、cluster 和多重选择的主要判断，但不同意把诸如：

> ≥30 terminal unique opportunities + ≥15 dates

误用成**新机制开始 Paper 的前置门**。

这只能是**开始做经济比较/晋级复审的 maturity checkpoint**。

如果一个候选：

- 机制与现有策略真实不同；
- 不增加新网络资源；
- 5U；
- 从新 frontier 开始；
- 明确 baseline；
- 缺数据 WAIT；
- 不影响旧策略；

那么让它开始产生严格前向样本，本身就是获取上述 15 天/30 opportunity 数据的方法。

所以：

**BLOCK PROMOTION ≠ BLOCK DATA GENERATION。**

---

## B. 对 ADVERSARIAL_RISK R1 的限定

风险 R1 要求盈利策略额外做：

- +2–5% execution stress；
- +5/+15/+30 秒 latency stress；
- amount-specific plausibility；

这些对**晋级主力/Live**很合理。

但我反对把它们全部升级成当前普通 5U Paper 的交易前置条件。

原因是用户已经明确冻结轻量：

`market mark +4% / -4% + original-pool truth`

架构。

如果现在因为反方审查又要求所有候选 exact-quote、深度冲击、延迟模拟，我们会把一个**研究候选筛选系统**重新改造成半成品 DEX execution simulator。

我的裁决：

- 普通 Paper：保持当前轻量合同；
- 晋级评审：增加 execution/cost/latency stress；
- amount-specific 证据：只在目前已有该能力的有限 surface 做 Shadow/辅助评价。

---

## C. 对 MICROSTRUCTURE R1 的限定

Microstructure R1 提出 `Cost-Clearing Impulse` 应寻找约 **+15%～30%** 级位移。

机制目标对，但我**不接受把 15%/30% 直接变成本轮 entry threshold**。

外部证据没有证明 15%、20% 或 30% 哪个是最佳值；这么做会重新进入 parameter selection。

目前唯一可以机械推出的是当前合同的**名义回本带**：

4% 买入 + 4% 卖出意味着观察市场价格需要约 **+8.33%** 才只是名义回本。

“候选应寻找明显超过成本的位移”成立。

“具体必须预测 +15% 或 +30%”则仍是待验证假设。

---

# 6. 根草案已有 8 个机制的 R2 裁决

| 现有代表 | R2 | 原因 |
|---|---|---|
| **1. l0_continuation_failure** | **KEEP / HIGH PRIORITY EXIT EXPERIMENT** | 当前唯一有轻微正 paired delta 的退出机制；仍整体亏损，因此只能说“少亏线索” |
| **2. l0_profit_lock** | **KEEP EXISTING, DO NOT PROMOTE** | 当前 paired delta -62.54U；已有实验即可继续，不需要复制新版本救结果 |
| **3. observed_cycle_reset_reacceleration** | **KEEP** | 与纯追涨机制不同；符合首波结束后另建 episode 的因果边界 |
| **4. volatility_scaled_depth_flow_momentum** | **KEEP WITH RENAMING/SEMANTIC DISCIPLINE** | 如果输入只是 volume/count/L0，不能继续称真实 pressure/flow；零新增资源、可继续 |
| **5. experiment_participation_candidate** | **CONDITIONAL KEEP** | 地址扩散比 txn count 更有意义，但 address≠person，且覆盖有限；输入不足是 coverage failure，不是机制失败 |
| **6. migration amount absorption** | **CONDITIONAL KEEP / HIGH VALUE** | 生命周期机制真正不同；只在 exact migration + 完整金额窗有资格，不能扩大成全链 |
| **7. clone_liquidity_leader** | **KEEP / HIGH PRIORITY** | 同时冻结 competing set，自带 contemporaneous control，是目前统计设计最干净的方向之一 |
| **8. observed_set_relative_resilience** | **KEEP / HIGH PRIORITY** | 真正增加 regime/横截面维度；必须继续叫 observed-set，不冒充全市场状态 |

这里我**不建议删掉任何已经运行的旧 arm**；“KEEP”指最终研究名单资格，而不是盈利资格。

---

# 7. 根草案新增 8 个机制逐项审查

## N1 突破后接受

**裁决：MERGE / NOT NEW BY DEFAULT。**

项目历史已经有：

- sustained breakout；
- mature acceptance；
- breakout/reclaim；
- cost-coverage runner。

如果所谓“突破后接受”只是：

`breakout → 等两个帧仍在上方 → BUY`

则很可能是旧 sustained-breakout / acceptance 的状态机改写，而不是第九种经济机制。

只有当 Codex 比较行为合同后确认它确实增加：

**“先跨越成本带 → 在新价格区域横向接受，而不是继续斜率上涨”**

这种行为差异时才可独立 ID。

否则直接复用/归并。

---

## N2 窄幅压缩释放

**裁决：REUSE EXISTING MECHANISM / ALLOW PAPER CONVERSION。**

历史证据地图已经明确存在：

`flat-compression-breakout shadow`

所以这不是新的经济想法。

如果以前一直 `decision_eligible=0 / affects=none`，可以：

- 保留原 Shadow 历史；
- 新建真正 Paper ID；
- 新 frontier；
- 明确这是 **Shadow hypothesis → Paper treatment**，不是“新发现的第九机制”。

**允许 5U Paper。**

---

## N3 回测区域承接

这里“回测”名称容易和 historical backtest 混淆，建议改名：

**Breakout-Retest Acceptance / 突破回踩承接。**

**裁决：MERGE WITH FAILED-BREAKOUT/POST-IMPULSE FAMILY。**

它和：

- failed-breakout reclaim；
- post-impulse survival；
- 双次下探吸收；

共享很大一块状态机。

最终不应三个都注册成“新机制”。

建议只保留一个：

**Shock/Breakout → controlled retrace → region holds → renewed acceptance → next-frame BUY**

作为反转/二次接受家族。

---

## N4 抛压减弱反弹

**裁决：KEEP AS LOW-COST DISTINCT EXPERIMENT，BUT DOWNWEIGHT。**

它与上面的价格形态不同，因为 treatment variable 是：

`sell count share 的方向变化`

而不是单纯价格收复。

但必须明确：

- sell count ≠ sell amount；
- raw volume 不能做逐笔 delta；
- wash/churn 可以制造笔数；
- 因此它属于 **L0 proxy experiment**。

如果后续 actual amountful flow 有完整覆盖，可以另比较：

`count-based exhaustion` vs `amount-based absorption`

但不能悄悄替换历史输入。

**允许 5U Paper；不允许作为主力。**

---

## N5 双次下探吸收

**裁决：DELETE AS SEPARATE ID / MERGE。**

它与：

- breakout-retest acceptance；
- failed-breakout reclaim；
- support-risk/reclaim

高度同质。

“双底”这个图形名称没有独立经济证据证明应占一个最终策略席位。

应把“两个分离低点仍守住区域”作为上述 **retest/reclaim family 的一个状态条件**，而不是另建一条最终机制。

---

## N6 流动性先增后重估

**裁决：NOT NEW — REUSE EXISTING。**

证据地图已经明确存在：

`liquidity_leads_price_v1`

所以这条不能再包装成“R2 新机制”。

现有版本继续自然前向即可。

另外维持语言纪律：

DexScreener/Gecko 的 liquidity USD 增长只能叫：

**reported pool liquidity increase**

不能叫：

- LP net deposit；
- capital inflow；
- smart money accumulation。

**允许现有小额 Paper 继续；不复制新 ID。**

---

## N7 首冲后缩量再启动

**裁决：MERGE WITH `observed_cycle_reset_reacceleration_v1`。**

两者核心都是：

`Impulse → cooling/reset → price survives → activity reaccelerates`

如果区别只是“缩量”替代某个 reset 指标，这是一个 feature specification，不足以天然构成两个终极机制。

建议最终保留：

**Post-Impulse Reset/Reacceleration**

一个家族。

可以在同一预注册策略里要求：

- 明确第一冲；
- 至少一个真实时间跨度的降温；
- 价格/liq 未结构性死亡；
- activity 重新上升；
- next independent frame 成交。

不要建立多个 15/30/60 秒 reset 参数臂。

---

## N8 阶梯式趋势持有

**裁决：REMOVE FROM ENTRY-MECHANISM LIST；KEEP ONLY AS EXIT/HOLD TREATMENT。**

它最主要改变的其实是：

> 已经入场以后允许更长的健康回撤和更长持仓。

这首先是 **exit experiment**。

而当前最直接的自然证据恰恰是：

`conditional_runner candidate − control = -84.84U`

所以没有理由再把“持久趋势”包装成全新入场 alpha。

如果保留：

- 与完全相同 entry 配对；
- 只改变 hold/exit state；
- 优先观察是否真的增加右尾，同时恶化多少核销/下尾。

**不建议现在再新增一条完整策略。**

---

# 8. 删并后，我建议的最终研究组合不是机械 16 条

我建议当前 R2 收敛到 **13 个机制/实验族**，已经满足用户要求的 10–20，而且正交性明显高于硬凑 16。

1. **Broad-entry + Continuation-Failure Triage**
   高召回/快速淘汰退出。

2. **Cost-Cleared Profit Preservation**
   已回本后的利润保存；现有负证据继续作为可证伪实验。

3. **Post-Impulse Reset / Reacceleration**
   合并 cycle reset + 首冲缩量再启动。

4. **Volatility-Normalized L0 Momentum**
   不把聚合量冒称真实资金流。

5. **Participant Expansion**
   动态地址扩散；coverage-conditional。

6. **Migration Absorption**
   生命周期切换后的真实 amountful absorption。

7. **Clone Liquidity Leadership**
   同题材冻结集合相对选择。

8. **Observed-Set Relative Resilience**
   弱环境中的相对强度。

9. **Compression → Release**
   从既有 `flat-compression-breakout Shadow` 转成新 frontier 5U Paper，而不是假称新机制。

10. **Retest / Failed-Breakout Acceptance**
    合并回踩承接、双次下探、failed-breakout reclaim。

11. **Sell-Pressure Exhaustion Rebound**
    先以 count proxy 小额实验；amountful 版本覆盖充分后再比较。

12. **Liquidity-Leads-Price**
    直接复用已经存在的 `liquidity_leads_price_v1`，不重复实现。

13. **Event → Market Acceptance**
    保留现有 exact official-event/actual-flow 资产：事件只产生 episode，入场必须等待后续市场接受。外部案例支持研究该机制，但不支持“有名人/新闻就买”。

### 不单列为完整策略，但必须保留的 treatment

- Profit lock exit；
- Longer trend hold；
- trailing；
- scale-out；
- fast stop；
- amount-specific execution overlay。

它们属于**退出/执行实验维度**，不要重新扩张成几十条“完整策略”。

---

# 9. 为什么我没有把“聪明钱包”列入当前 13 个优先机制

外部证据和本地统计现在对它都不友好。

本地：

`watched_wallet_confirmed_entry_control_v1`

目前是唯一当前期正闭环 arm，但：

- 只是 control；
- +4.83U；
- 中位数负；
- 去掉最好三笔即 -29.61U。

外部大样本钱包 cohort 研究又显示 activity-matched placebo 可以解释甚至超过所谓协调钱包的 buyer/flow lift。

因此钱包系列：

**继续已有 Shadow/5U experiment，可以；晋级主要候选，不可以。**

除非未来前向结果同时击败：

1. same-opportunity no-wallet control；
2. activity-matched wallet placebo；
3. waiting-cost/late-entry control。

---

# 10. 本轮底层有哪几个事实需要先保持正确

不要求大重构，只要求新候选不能绕过已经证实的几个底层边界：

### 必须保持

- 正价但 `liquidity=NULL` 不能算完整行情成功；
- stale/failed/429 不更新 success/observed time；
- sibling pool 不能代替 original pool；
- negative liquidity 不能通过入场；
- 信号帧不能同时成交，必须 next independent frame；
- 同一 timestamp 的重复帧不能伪造成“两次确认”；
- `volume/count` 是聚合窗口时，不能当逐笔 delta；
- address 不等于 human；
- reported liquidity change 不等于 LP deposit/withdraw；
- execution activation、成本、资金期分别冻结。

这些不是新增防御平台，而是已经发生过真实污染的直接边界。

---

# 11. 资源约束

我支持根草案的这条约束：

> 新 L0 候选不得为自己增加外网请求。

具体执行建议：

- 只复用当前最多约 80 帧/20 分钟的现有原池序列；
- 无足够基线 → `WAIT`；
- 不为了得到“双确认”提高全局采集频率；
- 用物理时间间隔而不是“连续两个 row”确认；
- candidate evaluation 必须是 O(已有局部序列)，不要扫全历史；
- 5U；
- 最多同时 4 仓；
- 研究任务优先级低于持仓行情/退出；
- wallet/amount-flow/migration 类只有当前已有完整覆盖时才运行；
- 不为了 13 个候选新增大型钱包索引、archive RPC 或历史分钟数据服务。

---

# 12. 是否允许小额 Paper？

**YES，但只是生成严格前向反证数据。**

我的批准条件：

### 可直接允许

- 已有输入；
- 真正行为不同；
- 新 deployment frontier；
- 5U；
- ≤4 concurrent positions；
- 无新增外网请求；
- 缺值 WAIT；
- next-frame execution；
- 有预定义 baseline/control；
- 不重置；
- 不回填。

这些候选不需要等待“先证明 alpha”——否则永远无法得到新样本。

### 暂不允许或只 Shadow

- 依赖当前没有稳定覆盖的完整 wallet history；
- 依赖全量 holder/hidden bundle；
- 需要把 current metadata 回填过去；
- 需要额外高频 archive RPC；
- 无法形成不同于旧策略的 behavior hash；
- 只有重新调一个阈值，没有不同机制；
- 无法定义普通/失败币分母。

---

# 13. 阻止盈利宣称 vs 阻止部署：明确区分

| 问题 | 阻止 alpha 宣称 | 阻止 5U Paper |
|---|---:|---:|
| 当前期只有1.29小时 | **YES** | NO |
| v22 单token极端集中 | **YES** | NO，新规则重新前向即可 |
| 当前候选整体亏损 | **YES** | 不自动；若机制尚未被干净否证 |
| 规则与已有策略行为等价 | YES | **YES，禁止重复ID** |
| 输入覆盖低但缺失被正确WAIT | YES/降级 | 通常 NO，条件型可运行 |
| 输入不存在而靠代理冒充 | YES | **YES** |
| 未来数据/ATH/赢家回填 | **YES** | **YES** |
| 新候选会抢持仓采集资源 | YES | **YES** |
| 只需要已有L0、5U、4仓 | YES，仍未成熟 | **NO** |
| 轻量Paper不证明真实成交 | **YES** | NO，这是当前冻结实验合同 |
| 明确工程污染仍未修 | **YES** | 对受影响机制 **YES** |

---

# 14. 晋级规则应比部署规则严格得多

这些候选开始 Paper 后，任何“alpha/核心策略”称号至少要等待：

- 多个独立日期，而不是 1.29h；
- unique token/episode，而不是账户成交数；
- matched baseline；
- chain/venue 分开；
- UNKNOWN/未成熟进入分母；
- Top1/Top3 contribution；
- remove-best-token robustness；
- paired ΔPNL；
- 下尾/writeoff；
- coverage；
- cost/execution stress；
- regime stability。

而且不能只在 13 个里面挑历史最好的那个再宣布发现 alpha——那只是把 multiple selection 往后推了一轮。

最终晋级规则应在看到未来结果**之前冻结**。

---

# 15. R2 external-research final verdict

### **PROCEED**

允许 Codex 从上述删并后的 **10–13 个真正不同机制家族**中，选择无需新增重资源、已有数据足够表达的候选做小额严格前向 Paper。

### **REVISE**

根草案的 8 个“新机制”不能原样全部作为新 ID：

- **突破后接受** → 与既有 breakout/acceptance 先做 behavior-hash 去重；
- **窄幅压缩释放** → 复用既有 flat-compression Shadow 机制；
- **回踩区域承接 + 双次下探吸收** → 合并；
- **流动性先增后重估** → 已有 `liquidity_leads_price_v1`，禁止重复；
- **首冲后缩量再启动** → 并入 cycle reset/reacceleration；
- **阶梯式趋势持有** → 降为 exit treatment；
- **抛压减弱反弹** → 可保留为一个真正新 L0 proxy experiment。

### **BLOCK**

阻止以下宣称：

- “历史已找到 alpha”；
- “V002 已证明优化成功”；
- “206/122 策略中排名最高者就是终极策略”；
- “钱包、social、名人、流动性增长单独能预测赢家”；
- “当前 Paper 利润等于实盘可实现利润”。

**最终 Codex 独立裁决；所有旧策略、资金期和历史保持，不重置。**
