[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-024100-OPEN-R1-EXTERNAL_EVIDENCE-RESULT  
REPLY_TO: C2C-20260907-024100-OPEN-R1-EXTERNAL_EVIDENCE  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: EXTERNAL_EVIDENCE  
SENSITIVE_DATA: NONE  

**DISPOSITION: NEW_EXTERNAL_SIGNAL_FOUND / PRIORITIZE_PATH_PERSISTENCE_AND_PUMP_FADE_DISCRIMINATION / NO_ALPHA_CLAIM**

模型：当前 Chat 为 GPT-5.6 Sol；实际推理档位无法独立核验，标记 **UNKNOWN**，不自称切换 GPT-6/xhigh。

### 1. 本地边界

已通过官方隧道只读实际读取：

`E:\memeTrader\docs\PROJECT_CONTEXT\RESEARCH_2026-09-07\ROUND2\RESEARCH_REQUEST.md`  
`E:\memeTrader\docs\PROJECT_CONTEXT\CURRENT_OBJECTIVE_AND_PLAN.md`

并继承上一轮已经冻结的 `HISTORICAL_STATISTICS / TOKEN_PRECURSOR_EVIDENCE / EXTERNAL_CORRECTIONS / FINAL_CONTRACT` 结论；没有重跑全历史扫描，没有改代码、DB、Runtime。

当前事实是 **214 策略保留、上轮8臂已部署、原 funding 不变**。当前 baseline 还存在严重的持仓行情覆盖/陈旧问题：研究请求记录 SOL quote-age P95≈345s、RH≈718s。因此涉及“持有多久/什么时候退出”的新自然证据，在评价前必须把 **market genuinely flat** 与 **provider 没更新**分开。这不是理由停止研究，但会直接污染“静默”“无进展”“价格持稳”类退出解释。

---

# 2. 本轮真正的新外部增量

上一轮主要集中在“毕业、钱包、操纵、12个著名案例”。本轮找到一个更贴近用户当前问题的新方向：

> **不是再问“什么币会涨”，而是研究第一波已经发生以后，哪些路径会继续，哪些会很快 pump-fade。**

这和 GXH 当前大量 entry 机制相比，对**持有/提前退出/利润奔跑**更有新增价值。

| 新证据 | 实际支持什么 | 不能推导什么 | GXH自然验证 |
|---|---|---|---|
| **SOLMEMES（ACM 2025/26）**：其 Solana 样本里，毕业币在发行后15分钟仍盈利的只是少数；文中报告顶部5% launch 的15分钟ROI约3×，而中位路径最优也约剩初始资金50%；毕业后越等待，median trades/ROI整体下降，但ROI离散度上升。毕业时间中位约5分钟、均值约11分钟。citeturn227146search12 | **首冲后的时间本身不是利好**；大多数路径衰减，但右尾随时间仍存在，所以固定“早卖一切”也会砍掉极端赢家。非常适合做“继续资格”而非仅 max-hold。 | 不能把论文的分钟数直接复制成5/11/15分钟阈值；它的样本、执行成本与GXH不同。 | 对相同entry，比较首次成本覆盖后：`progress persists / stagnates / reverses`；报告继续持有的右尾收益与增加的下尾损失。 |
| **新的 PumpFun Launch-to-Graduation Corpus**：39天、798,430 launch、33.58M trades、26.9M约15秒快照；毕业后另有1.39M DEX price/liquidity快照，5,669个毕业币被标成 `major_pump/minor_pump/sustained/pump_dump/dead` 并记录24/48h liquidity survival。citeturn279902view1 | 这是上一轮没有的非常直接的**持续赢家 vs pump_dump/dead 分母**，而不是只拿名币赢家讲故事。尤其适合研究毕业/迁移之后“哪种早期轨迹继续”。 | README 自己警告有数据质量问题，包括 wallet snapshot stale、regime break、curve-depletion overshoot；相关论文仍在进行，当前不能把README宣称的标签当同行评审结论。citeturn279902view2 | 如果根代理之后决定使用外部离线研究，可只做研究假设生成：比较相同毕业后前N分钟的价格持续性、liq retention、trade-velocity decay和buy pressure，再在GXH新frontier验证；**不要把这个历史数据直接训练成生产规则。** |
| **Galaxy 2025状态研究**：约12.8M Pump.fun token 中仅12个贡献平台总FDMC的55%以上；同时报告Solana token median holding time已降至约100秒，从约300秒下降。citeturn339182search2 | 极端赢家高度集中；市场参与者越来越短持。说明“等待长趋势”成本很高，同时赢家右尾又不能完全放弃。 | median hold time不是最佳持仓时间，更不是盈利策略；它包含交易者行为内生性。 | 研究**Earn-the-hold**：只有仍在产生新经济高点/相对强势/liq持续的仓位才延长，其他释放资本，而不是统一30/60min。 |
| **JFQA 2025 Pump-and-Dump**：P&D表现为价格、volume、volatility急增后快速反转，而且存在正式pump开始前的price run-up；自然实验还显示P&D会降低之后的liquidity和price。citeturn317141search0 | **“急涨+急量”恰恰可能是危险路径而不是持续赢家信号。** 持有资格必须判断 impulse 后的接受，而不能只因速度继续追。 | 研究对象不是Pump.fun新币，不能直接移植数值。 | 已跨成本的impulse后，对照 `继续加速`、`价格接受/liq保留`、`量继续暴增但价不再推进`；后者作为pump-fade候选。 |
| **Finance Research Letters 2024，1,457个P&D事件**：较低market cap、较低volume、较高social buzz及高市场波动与被pump概率相关；pump频率还有明显市场/日历因素。citeturn317141search1 | 同一绝对volume/价格模式在不同market regime意义不同；**不能按固定小时或固定volume阈值横跨regime。** | 不是Meme专属，更不能把“低volume”直接定义坏币。 | 把本项目已有 local observed-set activity/regime 作为**解释层/机会排序层**，不要重新搜“最佳小时”。 |
| **Twitter/P&D研究**：pump相关tweet数量在pump前与收益正相关，但在dump/post-dump阶段与收益负相关；受Twitter影响的参与者还表现出延迟退出和更大损失。citeturn317141search4 | attention 可以解释第一波，却不等于继续持有理由；**传播增强但价格进展失败**是值得退出的状态。 | 不能认为任何X热度增加都表示操纵；也不能要求GXH马上重建社交平台。 | 当未来已有信息事件时，把 social/event 只作为episode起点；持仓是否继续仍由价格/liq/市场接受决定。 |
| **SOLMEMES的另一关键结果**：毕业后的交易数和ROI的中位数随时间衰减，同时ROI方差扩大。citeturn227146search12 | 这给一个不同于固定TP的机制：**随着时间过去，继续持有需要越来越强的“继续资格”**。 | 不支持按年龄机械越来越紧的数字门槛。 | 新策略可比较“固定maxhold”与“progress-conditioned survival”：没新经济高点/相对韧性/liq保持则退出，有则延长。 |

---

# 3. 一个很重要的新反例：高 activity 可能恰好意味着快结束

上一轮以及本地 `TOKEN_PRECURSOR_EVIDENCE` 都看到，暴涨币的5m volume/count/buy-ratio在边际上有时更高，但分层稳定性很差。

本轮新文献进一步说明原因之一：

**P&D 的典型形态本来就是 price + volume + volatility 同时爆炸，然后迅速反转。** citeturn317141search0

所以我不建议再设计：

`volume更大 + buys更多 → 多持有`

这种简单延续机制。

更有经济区别的是：

**Activity conversion efficiency**

也就是：

> 新增活动有没有继续转化成新的价格进展？

例如，同样 `volume↑ / tx↑ / buy-share↑`：

- A：价格同时继续创造成本后新高、liq不坏 → **有效需求延续**；
- B：活动继续放大但价格推进越来越小/开始下降 → **activity failure / distribution candidate**。

这和已部署 `finalist_activity_failure_v1` 有亲缘关系，所以**不建议简单重复注册**；更值得根代理检查它是否只做了短时两帧退出，还是还能扩展成一个真正不同的“活动→价格转换效率”持有资格机制。

---

# 4. 本轮最值得新增研究的机制，不是另一套 breakout

我认为有四个实质增量，且都可以利用当前已有数据，不要求新API。

### A. Economic Progress Efficiency / 经济进展效率

**假设：**持续赢家不只是活动旺盛，而是每单位新增市场活动仍能产生新的成本后经济价值。

可获输入：

`price、volume5m、buy/sell count、reported liq、position economic value、time`

不需要逐笔资金流。

状态可以只比较严格相邻独立观察：

`Δeconomic_value / Δactivity`

但不要把 rolling 5m volume 差直接叫净成交量；最安全的第一版甚至不做数学比率，只识别：

**activity显著上升 + economic value没有实质进展**

作为 failure state。

**反证：**如果这类币随后反弹概率/费后收益与普通横盘无差异，或者滚窗机械变化产生大量假信号，则否决。

**下一自然验证：**共享同entry做 `activity-failure early exit` vs baseline，按token/cohort聚类比较净PNL、右尾遗漏和持仓资本时间。

> 注意：若与现有214中的 `finalist_activity_failure_v1` 行为实质相同，则**禁止重复ID**，改为研究该现有策略的自然结果即可。

---

### B. Conditional Survival / Earn-the-Hold Clock

这是我认为本轮**最有价值**的持有方向。

不是：

`买了 → 固定15/30/60分钟`

而是：

`只要它还在证明自己，就继续持有；失去证明才启动退出时钟。`

“证明自己”只能用当时已知东西，例如：

- 新的**净经济值高点**；
- 相对局部市场仍抗跌；
- liquidity没有恶化；
- 活动没有彻底衰竭。

SOLMEMES 对“随时间中位路径衰减但右尾扩散”的观察非常适合这类设计。citeturn227146search12

**反证：**如果赢家经常经历3–10分钟没有任何进展才突然第二冲，那么 progress clock 会错杀右尾。

因此下一自然验证不能只看平均PNL，还必须报告：

- 被提前卖掉后5m/15m结果；
- top-right-tail missed；
- capital-time released；
- 同entry baseline最终净PNL。

用户已经明确允许退出后的5/15分钟作为**研究标签**，这正好适用于验证这个机制，不能反填当时退出规则。

---

### C. Impulse Acceptance vs Exhaustion

和已有 boundary retest 不完全相同。

目的不是寻找特殊K线图，而是在**已经发生明显第一冲之后**分类：

`接受 / 尚未决定 / 衰竭`

**接受：**
价格在较高区域保持，liq没有破坏，活动下降但价格不回落明显。

**衰竭：**
volume/activity依旧很高，但新增活动无法推动价格继续，随后开始跌。

这与P&D文献的“巨大price/volume/volatility后快速reverse”直接相符。citeturn317141search0

关键新点不是“再找一个breakout”，而是：

> **降温但价格守住，可能比继续爆量更健康。**

这对Meme很反直觉，但很值得实验。

**反证：**普通成功winner如果持续爆量而不需要cooling，则这个规则会晚买/错过。

**验证：**同一第一冲episode冻结后分别记录：
`hot continuation / cool acceptance / hot-no-progress`，先Shadow分类；只有行为分母足够再注册Paper。

---

### D. Post-Graduation / Post-Migration Survival State

新发现的39日Pump.fun corpus最大的价值，就是它第一次给出了一个公开的、目的不是只选赢家的：

`major_pump / minor_pump / sustained / pump_dump / dead`

毕业后结果分母，以及连续price/liquidity快照。citeturn279902view1

这支持一个非常具体的问题：

> **毕业/迁移不是BUY信号，而是新的风险时钟起点。**

当前项目已有 migration、reawakening 和 lifecycle 相关资产，没必要新建大系统。

值得验证的是真正状态：

`migration → 初始价格发现 → liquidity survives? → activity converts to progress?`

而不是：

`migration happened → bullish`

**反证：**若 migration 后继续赢家与 pump-fade 在前几分钟完全不可分，则不要增加新策略。

**下一自然验证：**先用本项目已有迁移/场所样本做严格前向，外部 corpus 只用于生成变量定义，不用于“优化出”阈值。

---

# 5. “普通、失败、快速死亡”本轮新增对照

一个较新的独立观测研究跟踪了5,014个**选择性、非随机**Solana token结果：24小时约11.8%被判dead；低于$100k cap组的死亡率约48.9%，而>$1M约4%。作者自己明确说这不能证明市值造成死亡，并且另有1,657个 unresolved 被排除。citeturn227146search13

这个来源权威性远低于同行评审论文，所以我只把它当**反例设计提示**：

- “还没死”绝不等于赢家；
- “market cap较高”混合了年龄、流动性和生存选择；
- UNKNOWN/unresolved 绝不能删掉；
- 必须把快速死亡和“正常但不涨”分开。

这与GXH已有分母纪律完全一致，不建议把其市值数字做交易阈值。

---

# 6. 一个可利用但目前不该直接接生产的外部数据资产

本轮新发现的 `Pumpfun_Memecoin_Corpus` 很可能是下一次外部机制研究最有价值的数据源，因为它包含：

- 全量窗口launch而不是名币筛选；
- 15秒级pre-graduation snapshots；
- trade-level buy/sell；
- post-graduation price/liquidity；
- pump_dump/dead/sustained outcome。citeturn279902view1

但 README 明确存在 quantified known issues，且其三篇主要论文仍处于“in progress”，包括 rug survival、launch prediction、creator economics。citeturn279902view2

所以我的建议不是现在下载几十GB/上TB数据并训练模型，而是：

**只有根代理后续确实需要验证某个具体机制时，才读取其 KNOWN_ISSUES 和最小必要表，做离线 hypothesis falsification。**

不要为了“研究全面”把它变成新基础设施。

[PumpFun Launch-to-Graduation Corpus](https://huggingface.co/datasets/Slinky21/Pumpfun_Memecoin_Corpus?utm_source=chatgpt.com)

---

# 7. 对现有214最重要的现实约束

本轮外部研究让我更担心的不是“策略数量太少”，而是**持仓真实观察年龄**。

因为很多最佳新假设依赖：

`价格没动 / activity仍增加 / liquidity保持 / progress停止`

但如果 SOL/RH 部分 held quote 数分钟不新鲜，那么：

> “没有进展”可能只是**没有新的市场证据**。

因此任何 Conditional Survival / progress / pump-fade exit 必须继续坚持：

**fresh valid observation clock，而不是 wall-clock。**

数据断流：

`UNKNOWN / reset`

不能：

`stagnation`

这个原则应当比新增多少策略更优先。

---

# 8. 当前外部证据排序

我不建议下一轮再大规模追逐名人、钱包或历史名币案例。当前最值得根代理进一步裁决的顺序是：

1. **Progress-conditioned hold / Earn-the-Hold**  
   解决“什么时候允许长持右尾”。

2. **Activity-to-price conversion failure**  
   解决“爆量到底是延续还是distribution”。

3. **Impulse cooling/acceptance vs hot exhaustion**  
   解决“第一冲之后是否追、等还是退”。

4. **Migration/post-graduation survival state**  
   解决生命周期切换以后pump-fade。

5. **Relative opportunity/capital rotation**  
   只有前四项有可用自然证据后，再研究有限资金下哪个机会值得占槽。

其中1–3大部分都可复用现有 mark/L0 数据，**不需要任何新API**。

---

# 9. 不支持的结论

本轮没有找到：

- 一个可直接证明持续赢家的单一前置feature；
- 一个应该把全部214策略改掉的统一规则；
- 一个经外部验证可直接加资金的alpha；
- 一个“最佳持仓分钟数”；
- 一个可以把高volume/high buy ratio直接解释成健康需求的依据。

相反，新证据最一致地提示：

> **第一波上涨本身很容易制造假阳性。真正可能产生增量的是第一波之后，活动、价格、流动性与时间之间是否继续保持“有效转换”。**

这也是我建议 Round2 外部研究主线从“更多entry pattern”转向：

**谁值得继续持有，谁应该尽快释放资本。**

原214全部保留；不初始化、不覆盖、不改运行。Codex根代理继续作为唯一writer与最终裁决者。 citeturn227146search12turn317141search0turn279902view1
