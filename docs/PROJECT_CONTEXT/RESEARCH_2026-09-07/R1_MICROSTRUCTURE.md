# R1 MICROSTRUCTURE

Source Chat: 6a9d94bd-ef58-83ee-836b-36251dadab7a
Retrieved: 2026-09-07 Asia/Shanghai
Actual Chat response; model self-description is not host-verified model metadata.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R1-MICROSTRUCTURE-RESULT
REPLY_TO: C2C-20260907-R1-MICROSTRUCTURE
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: MICROSTRUCTURE
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

## 1. REVIEW STATUS

**DISPOSITION: REVISE / PROCEED_WITH_BOUNDED_CANDIDATES**

本轮已实际通过 **笔记本量化MCP-官方隧道**只读访问 `E:\memeTrader`。未修改代码、数据库或 Runtime；未访问 `config.json`/secret；未运行大量 SQL，事实上本轮**没有运行 SQL**；未读取其他 reviewer 的 R1 结论；`HISTORICAL_EVIDENCE_MAP.md`、`HISTORICAL_STATISTICS.md` 等仍在生成，本轮没有将其作为已完成证据。

Chat 模型/推理档位：**未核验**。不能据模型自述确认 GPT-6/xhigh。

---

# 2. 核心结论

从交易微观结构角度，当前系统最应该避免的错误，不是“4%滑点够不够保守”这么简单，而是把以下四件事混成同一件事：

**Token 还有市场价 ≠ 原持仓池还有可卖流动性 ≠ 当前数量能以该价退出 ≠ 流动性下降就是 LP 被撤。**

项目最近的工程修复已经朝正确方向移动：原池身份、缺 liquidity 不再算成功、另一池不能替代原池成交、UNKNOWN/429/陈旧不能直接核销。这些不是次要工程细节，而是对 Paper 经济含义成立与否的基础。

同时，我**不建议推翻用户刚冻结的轻量 Paper 合同**。普通策略继续：

`原池新鲜价格 → BUY +4% → 持有 → SELL -4%`

是合理的统一研究基线。不要因为微观结构审查又把所有普通策略升级成逐笔深度/精确 quote 平台。

但这意味着一个非常重要的评价约束：

> **当前 Paper 的收益只能解释为“固定双侧成本下的轻量市场路径表现”，不能解释为真实可执行利润。**

这两个口径必须始终分开。

---

# 3. PROJECT FACTS — 本轮实际核验的项目事实

### PF-01：当前执行成本是非对称复利门槛，不是简单“8%涨幅回本”

`paper_execution.py` 当前默认：

- BUY slippage = 4%
- SELL slippage = 4%
- 每 fill 额外费用 = 0
- 原池最低 liquidity = 1000 USD

20U BUY 时取得：

`quantity = 20 / (market_price × 1.04)`

SELL 时：

`proceeds = quantity × later_price × 0.96`

因此忽略额外费用时，市场价格至少需要：

`1.04 / 0.96 = 1.083333...`

也就是相对入场观察价约 **+8.33%**，才只是 Paper 的名义盈亏平衡。

所以对于 Meme 的短周期策略：

- +5% 的方向判断即使完全正确，Paper 仍亏；
- +8% 左右基本没有经济意义；
- +10% 也只剩很薄的容错；
- 真正有价值的 entry 必须寻找能够产生**明显超过成本带**的位移，而非小幅预测正确。

这解释了为什么“胜率”“方向正确率”不能代替费后结果。

### PF-02：当前普通 Paper 明确采用线性价格模型

当前 `buy_terms()` 是观察价 × `1+4%`；`sell_terms()` 是观察价 × 数量 × `1-4%`。

没有按池储备计算 20U 的实际 price impact。

这是**用户明确接受的轻量 Paper 合同**，不是本轮应强制修掉的 defect。

但当池极小时，固定 4% 与真实数量冲击可能严重偏离，因此 1000U 原池 floor 的作用不仅是 rug 过滤，也是对该线性模型适用范围的最低防护。

### PF-03：原池身份已经证明是实质经济变量

项目已有真实记录：

`cohort12154`

- TP 触发后到第一份留存的合格**原池** post-frame：约 **77.267 秒**；
- 合格帧出现后约 **0.924 ms** 即 fill；
- 约 **9.717 ms** 后 trade 落库；
- 中间存在其他池行情，但不能替代原持仓池执行；
- 后续核销；
- 约 20U 仓位净损失 9.18U。

因此这个案例支持：

**不是本地 Paper fill 算得慢，而是“可接受的原池观测”出现得晚。**

但项目证据还不足以证明那 77 秒期间真实链上一直不可卖，所以也不能反过来声称是确定的执行损失。

### PF-04：当前缺 liquidity 的正确语义已经收紧

最新权威状态明确：

- 正价格 + `liquidity=NULL` 不再算完整成功；
- 不允许 NULL liquidity 覆盖旧完整帧；
- 失败不刷新旧帧 `observed_at`；
- 缺失/失败/陈旧不证明池死亡；
- known fresh liquidity < floor 才进入 dust/writeoff 语义。

这对经济统计非常关键：

过去把“不知道”解释成“还能卖”或者“池死了”，都会系统性扭曲收益。

### PF-05：项目已经有真实的成本后回吐现象

`BROAD_COST_COVERAGE_SCALEOUT_RESEARCH_2026-09-05.md` 记录的清洁设计样本：

- 1,865 个终局；
- 199 个运行中经济高点曾达到 +12%；
- 其中 **109 个最后 realized PNL 为负**；
- 155 个曾达到 +30%。

这不是 scale-out 能赚钱的反事实证明，但足以说明：

> **“已经跨过交易成本并出现明显盈利，然后全部吐回”是真实存在的结构问题。**

因此“盈利后如何保存收益”比继续微调 entry liquidity 门更值得研究。

### PF-06：已有资金流类策略比纯买卖笔数更接近正确微观结构

当前已经实现/研究的输入包括：

- actual net flow；
- amount-weighted breadth；
- 最大地址资金占比；
- churn；
- creator 实际卖出金额；
- bundle-adjusted breadth；
- migration 后卖压衰减；
- Vault 流出；
- 价格相对实际资金流的 fragility。

这些比单纯 `buys > sells` 更有经济意义，因为 100 次 0.01U BUY 完全可能敌不过 1 次 50U SELL。

但当前免费采集也有明确限制：

- 热池超过 10 signatures 的窗口可能截断；
- 完整 actual-flow 需要两份可证明覆盖的相邻窗口；
- pre-graduation 完整资金流受付费 API 限制；
- 地址不等于独立自然人；
- 隐藏跨交易 bundle 无法完整恢复。

不能把“有部分 flow 数据”冒充“完整订单流”。

---

# 4. EXTERNAL EVIDENCE — 独立外部机制证据

### EE-01：不同池机制绝不能使用同一个“撤池风险”解释

Raydium CPMM 官方文档明确存在 `Withdraw`：LP 持有人销毁 LP token，并按比例取回两边资产。也就是说 CPMM 中 LP 控制权本身具有直接的流动性退出能力。citeturn111028search1

Raydium CLMM 则不同。它是基于价格区间的集中流动性，LP 由 position 表示，并存在 `DecreaseLiquidity`。因此：

**池总 TVL 仍存在，也不代表当前价格附近仍有相同有效深度。**

价格跑出 LP range 或流动性集中区迁移，都可能让当前交易表面的有效深度恶化，而不是简单的“整个池被撤”。citeturn111028search2turn111028search3

### EE-02：Pancake V2/V3 同样允许 LP 主动撤流动性

Pancake 官方界面明确支持移除部分或全部流动性；V2 Router 也有明确的 `removeLiquidity`/`removeLiquidityETH` 路径。citeturn111028search0turn111028search6

所以对 BSC：

> “liquidity 突降”不能直接叫 rug，但“LP 可撤”确实是协议能力，必须和 sell drain、迁移、API失观测分开。

### EE-03：PumpSwap 普通池与 canonical migration 不应混为一类

PumpSwap SDK 本身有 deposit、swap、**withdraw** 接口，所以一般 PumpSwap 池并不存在“天然不可撤”的普遍结论。citeturn759287search0

项目历史研究把 **Pump bonding curve migrate 形成的 canonical Pump pool** 与普通 PumpSwap pool 分开，是正确方向。

由于 Pump 协议 2026 年仍持续发生账户布局、fee、pool 结构更新，不能把旧版协议假设永久冻结；官方仓库 2026 年仍有多次 fee/pool 更新。citeturn759287search5

这也支持项目的原则：

**surface/version/protocol identity 应保留，而不是只记一个 `dex_id=pumpswap`。**

---

# 5. STATISTICAL FINDINGS — 本轮可引用与不可引用的统计

本轮没有运行新的全历史 SQL，因此**没有产生新的全项目统计结果**。

目前可以引用的只有已经完成并实际读取的历史材料中的有限统计：

1. Broad cost coverage 清洁设计样本的 `1865 / 199 / 109 / 155`；
2. cohort12154 的约 77.267 秒原池 post-frame 延迟；
3. 一个已核对的真实 clean Paper 例：

`broad_cost_coverage_scaleout_v1 / cohort12309`

- BUY：20U；
- 信号价格约 `1.59e-6`；
- +4% BUY price `1.6536e-6`；
- 后续原池 `9.082e-7`；
- SELL 再扣 4%；
- 回款 `10.5451U`；
- 净亏约 `-9.4549U`。

这些只能证明成本模型和个别生命周期真实发生，不能证明某一种 entry alpha。

**明确未使用：**

- `HISTORICAL_STATISTICS.md`：生成中；
- `HISTORICAL_EVIDENCE_MAP.md`：生成中；
- 其他 reviewer R1；
- 未成熟的本地全历史重算。

---

# 6. MICROSTRUCTURE DIAGNOSIS

我认为后续统计必须把失败至少拆成以下经济机制，而不能只用 `SELL / WRITEOFF / LOSS`：

**A. PRICE_DECAY**
原池仍健康，买盘衰退/卖盘占优，正常价格下跌。

**B. SELL_DRAIN**
LP 没撤，但持续卖出把 quote reserve 抽走。

**C. LP_WITHDRAWAL**
有协议级 withdraw/decrease-liquidity 证据。

**D. RANGE_LIQUIDITY_LOSS**
CLMM 池仍存在，但当前价格附近有效流动性显著消失。

**E. MIGRATION / PAIR_SWITCH**
旧池流动性下降伴随明确新 canonical surface 出现。

**F. ROUTE_DISAPPEARED**
当前余仓无法得到有效执行路径，但还不足以证明 LP 被撤。

**G. PROVIDER_UNOBSERVABLE**
429、NULL、缓存、覆盖缺口或错误；必须保持 UNKNOWN。

**H. PAPER_MODEL_FAILURE**
观察价存在，但在极小流动性环境下 mark±4% 明显超出轻量模型可信范围。

否则会发生两种严重错误：

- 把工程/供应商失观测当成 rug；
- 把真正的 LP/有效深度崩塌当成普通价格止损。

---

# 7. 对 1000U 原池 floor 的判断

**不建议把“提高统一 liquidity floor”当本轮主要优化方向。**

理由：

1. 1000U 已经承担防止最荒谬线性成交的作用；
2. 再机械提高到 3k/5k/10k，很可能把真正能产生 Meme 凸性收益的早期阶段一起过滤掉；
3. liquidity 高本身并不证明安全；
4. liquidity 低本身也不证明没有正期望；
5. 同样 3000U：
   - canonical Pump；
   - 用户可撤 PumpSwap；
   - Raydium CPMM；
   - Raydium CLMM；
   - Pancake V2
   具有完全不同的风险含义。

因此后续应优先研究：

**liquidity 的方向、来源、持续性和控制权，胜过单纯 liquidity level。**

---

# 8. 候选策略/机制 — 当前采集能力能够支持

以下候选都不要求把系统升级成 order-book/逐笔成交平台。

### C1 — Cost-Clearing Impulse

核心不是“价格上涨”，而是：

`价格动量 + 净资金流 + 广度`

必须足以跨过约 +8.33% 的最低成本带，并给风险留余量。

建议 candidate 目标不是预测 +3/+5%，而是寻找具有 **+15%～+30% 级潜在 impulse** 的状态。

不是简单把 gate 变严，而是把策略目标从“方向正确”改成“位移足够支付交易”。

### C2 — Cost-Cleared Profit Preservation

直接利用已经存在的成本后回吐问题。

机制：

- 先达到真实完整账户成本后盈利；
- 兑现一部分；
- 余仓依据运行高点回撤/flow 弱化退出；
- 不使用未来 ATH。

这是我认为优先级很高的候选，因为当前已有明确现象支持研究问题存在。

### C3 — Liquidity-Flow Divergence Exit

持仓价格仍上涨，但：

- net inflow 下降；
- 大额买家广度下降；
- liquidity 减少；
- sell amount 占比上升。

这种情况下不等价格 hard stop 才退出。

它与 `price_to_flow_fragility` 同族，建议保留一个真正行为差异版本，而不是堆多个阈值变体。

### C4 — Sell-Drain Early Exit

不要求证明 LP rug。

若：

- 原池身份稳定；
- liquidity/quote reserve 连续恶化；
- 实际 SELL 金额明显超过 BUY；
- price 与 quote reserve 同向恶化，

则按 **sell-drain** 机制快速退出。

它与“LP 被撤”完全不同，因此值得独立策略/退出族。

### C5 — Liquidity Survival / Recovery

入场后不是只看绝对 liquidity，而看：

`L_t / L_entry`

和最近若干独立帧的趋势。

有意义的是：

- liquidity 持续增长；
- 冲击后能够重建；
- price 回撤但 liquidity/flow 没坏；
- liquidity 先坏于 price。

避免把同一个 `3000U` threshold 复制到所有策略。

### C6 — Migration Absorption

项目当前已有相关输入，值得继续，但必须坚持：

`canonical migration → 初始冲击 → 回落 → 卖压衰减 + liquidity重建 + 实际flow恢复`

而不是“迁移即买”。

这属于真正不同生命周期阶段。

### C7 — CLMM Surface Risk

仅在确认 CLMM 的候选上启用。

不要企图完整计算 tick depth；当前架构不值得这样膨胀。

最低成本做法是：

- 单独 surface 标签；
- 当前原池 liquidity/path 连续性；
- 突然出现价格变化而 pool liquidity/route 可用性异常时作为风险 tier。

如果无法取得可靠 range 状态，则保持 UNKNOWN，不制造“CLMM安全评分”。

### C8 — Executable-Recovery Exit Overlay

仅对当前已有 amount-specific quote 能力的 Solana 小范围策略。

它不是替代全局 Paper，而是对照：

`mark×0.96 理论余仓价值`
vs
`当前真实数量可获得的 minimum output`

研究两者偏差什么时候开始失控。

如果偏差持续扩大，就作为提前退出/降仓候选。

### C9 — Broad High-Recall + Fast Economic Triage

我支持继续保留宽入口臂，而不是把所有策略越做越严。

逻辑：

`宽入口 → 60–120s 按成本后价格/真实flow/liquidity复审 → 不合格快速退出`

原因是 Meme 的凸性意味着，过强的 universal pre-entry gate 很容易删除真正的大赢家。

“早进、快速淘汰”与“严门后进”应该作为独立机制对照。

### C10 — Wave Reset / Reawakening

继续遵循项目现有假设：

第一次 impulse 死亡以后不硬扛等待第二波。

真正平仓后，如果出现：

- 新资金；
- liquidity 重建；
- breadth 恢复；
- 新局部价格结构，

把它作为一个**新的严格前向 cohort**。

这是比把 max-hold 从 15 分钟调成 30/60 分钟更干净的机制。

---

# 9. 我不建议做的事情

**不建议：**

- 所有策略统一升级 exact quote；
- 为所有池做完整 reserve-depth simulator；
- 建逐笔订单流平台；
- 把 liquidity threshold 从 1000 一路参数喷射到 2k/3k/5k/10k；
- 用 buys/sells 笔数直接代替资金流；
- DexScreener liquidity 跌 90% 就标记 rug；
- 另一池存在价格就认为原仓可退出；
- API missing 就核销；
- 为了解决退出现实性，把普通 Paper 复杂化到资源无法承受。

这些会把项目从“可长期运行的 Meme 策略实验系统”变成“半完成的 DEX 模拟器”，投入产出比不合适。

---

# 10. R2/R3 最值得裁决的问题

1. **是否把“成本足够大才值得预测”正式作为策略设计原则？**
   即普通 4%+4% Paper 下，不再把小幅方向预测当主要 alpha。

2. **是否把 liquidity 从单值 gate 升级为生命周期变量？**
   level / slope / survival / recovery / collapse mechanism 分开。

3. **是否要求全历史统计按 market surface 分层？**
   至少 Pump canonical、Pump noncanonical、Raydium CPMM、Raydium CLMM、Pancake V2/V3、unknown 不应混成一锅。

4. **WRITEOFF 是否必须与经济失败类别分开统计？**
   `confirmed low-liquidity terminal`、`route disappeared`、`provider unknown`、`engineering contaminated` 不能混合。

5. **是否把 Cost-Cleared Profit Preservation 提到最终候选组合前排？**
   因为当前已有实际“曾盈利→最后亏损”的证据，而不是凭空创造方向。

6. **是否继续保留宽入口 + 快速淘汰臂？**
   我倾向 **YES**；不能把所有优化都变成提高入场门槛。

7. **是否只将 amount-specific executable quote 作为 challenger/overlay？**
   我倾向 **YES**，遵守用户轻量 Paper 合同。

8. **最终 10–20 策略是否限制同机制阈值克隆？**
   建议限制。最终组合应覆盖不同经济机制，而不是 20 个 liquidity/momentum 数字组合。

---

# 11. 实际读取路径

本轮实际读取：

`E:\memeTrader\AGENTS.md`

`E:\memeTrader\.agents\skills\memetrader-forward\SKILL.md`

`E:\memeTrader\docs\PROJECT_CONTEXT\RESEARCH_2026-09-07\REVIEW_SCOPE.md`

`E:\memeTrader\docs\PROJECT_CONTEXT\CURRENT_OBJECTIVE_AND_PLAN.md`
读取当前权威首段及相关历史阶段，不声称全文所有 700+ 行均重新审阅。

`E:\memeTrader\docs\PROJECT_CONTEXT\ARCHITECTURE_AND_DATAFLOW.md`

`E:\memeTrader\docs\PROJECT_CONTEXT\CHATGPT_CODEX_IMPLEMENTATION_HANDOFF_MEMETRADER_SYSTEM_RESEARCH_2026-09-03.md`

`E:\memeTrader\docs\PROJECT_CONTEXT\CAPITAL_18_DIRECTIONS_2026-09-06.md`

`E:\memeTrader\docs\PROJECT_CONTEXT\BROAD_COST_COVERAGE_SCALEOUT_RESEARCH_2026-09-05.md`

`E:\memeTrader\src\memetrader\paper_execution.py`

另外通过只读 grep 检查了 `src/memetrader/*.py` 中 slippage / WRITEOFF / liquidity / quote 相关实际接线位置。

外部独立核验了 PumpSwap、Raydium CPMM/CLMM、PancakeSwap 流动性机制的公开资料；这些属于 **EXTERNAL EVIDENCE**，没有与项目事实混写。

---

## FINAL R1 JUDGMENT

当前系统不需要再造一个复杂成交平台才能继续研究。

真正需要收敛的是：

**原池身份正确 → UNKNOWN 不乱解释 → 按 market surface 理解 liquidity → 用资金金额而不是交易次数描述买卖压力 → 所有策略首先跨过成本带 → 盈利后重点研究如何避免回吐 → 第二波重新入场而非死扛。**

在最终 10–20 个策略中，我建议至少保留 **5–7 个彼此不同的微观结构机制族**，而不是把几十个历史模板用更严格门控重新包装。

**R1 微观结构评审完成；等待 R2 共同证据/交叉质疑。**
