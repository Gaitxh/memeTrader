[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-024100-OPEN-R1-CAUSAL_REGIME-RESULT  
REPLY_TO: C2C-20260907-024100-OPEN-R1-CAUSAL_REGIME  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: CAUSAL_REGIME  
SENSITIVE_DATA: NONE  
MODEL: GPT-5.6 Sol；实际推理档位/产品配置 **不可核验**，不声称已切换其他模型。

## 结论

**DISPOSITION: CONTINUE_OPEN_MECHANISM_RESEARCH / NO_TIME_ALPHA / NO_PROMOTION**

这一轮最值得研究的新东西，不是“哪个小时最赚钱”，而是：

> **一个机会在入场时处于什么可观察状态，以及退出时处于什么状态；日期/时段只作为这些状态发生频率改变的背景变量。**

当前证据不支持直接把 UTC 小时、星期、日期设成交易门；但强烈支持把 **市场活跃度、机会密度、池龄构成、liquidity层级、买卖结构、数据完整性、近期右尾/死亡比例** 组合成前向 regime 状态，再验证同一策略机制在不同 regime 下是否异质。

---

# 一、实际读取

通过官方隧道只读：

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/ROUND2/RESEARCH_REQUEST.md`
- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/TOKEN_PRECURSOR_EVIDENCE.md`
- `src/memetrader/` 中与现有 5m volume、buys/sells、pool/liquidity、pattern/outcome 数据相关代码位置的有界检索
- 工作区 `AGENTS.md`

ROUND2 目录当前只有 `RESEARCH_REQUEST.md`；`PATH_AND_REGIME.md / FOUNDATION_REVIEW.md / EXTERNAL_NEW_EVIDENCE.md` 此刻尚未落地，因此以下不冒充已读取这些未来报告。

没有重跑全历史扫描，没有修改代码/DB/Runtime，没有另开 writer。

---

# 二、已确认事实

### F1. 时间效应当前不可直接识别为 alpha

上一轮冻结 `TOKEN_PRECURSOR_EVIDENCE.md` 已经证明：

chain-meme 暴涨 vs 普通的：

- volume5m
- buy ratio
- tx count

边际差异很大，但冻结成：

`chain × UTC 12h × pool-age × liquidity`

后只有少数可比较层，而且方向混合。

更严重的是：

**暴涨 vs 失败没有任何一个冻结层同时达到双方各≥3个样本。**

所以：

> “晚上更好”“凌晨更差”现在最多是 composition effect 候选，不能当策略事实。

**来源：上一轮冻结研究。**

---

### F2. 缺结果高度依赖时间和采集年代

旧 universe：

- 229,500 cohort
- observed baseline 93,075
- 明确 missing 40,336
- 无 baseline 行 96,089
- 60m outcome 实际只覆盖到 9月3日，而 cohort 延续到9月6日

因此某些日期“失败少/赢家少”可能仅因为 **outcome 尚未采到**。

**来源：TOKEN_PRECURSOR_EVIDENCE。**

---

### F3. 当前214账户自然证据仍非常早

当前权威起点：

- 214策略
- 原 funding 保留
- 上轮8臂 frontier 1214643
- profit_budget 当时20 BUY / 16终结 / +4.394U
- 但样本不足且可能 winner-concentrated

同时 SOL/RH 的持仓报价 age/coverage gap 仍很严重。

因此新一轮研究必须把：

**market regime**  
和  
**data-quality regime**

分开。

否则“某时段亏损”可能实际上只是该时段报价老化更严重。

**来源：CURRENT_OBJECTIVE_AND_PLAN / ROUND2 request。**

---

# 三、我建议把 regime 拆成5个前向维度

不搜索事后最佳组合，只冻结粗层。

## R1 — Opportunity intensity regime

当时过去固定窗口内：

- 新 token / pool arrival rate
- eligible pattern count
- 实际新 episode count

例如只分：

`LOW / NORMAL / SURGE`

假设：

**SURGE 时 broad/high-recall 可能需要更严格淘汰，但相对/leader策略机会更多。**

反证：

如果同链、同池龄/liquidity后，策略差异不随机会密度变化，则删除此regime。

---

## R2 — Market activity regime

使用当时已有整体横截面：

- median volume/liquidity
- median transaction activity
- buy-ratio distribution
- active-pool proportion

不使用未来收益。

假设：

- 高活动 regime 更适合 breakout / relative leader；
- 低活动 regime 更适合 reawakening；
- 极端高活动也可能是 manipulation/churn regime。

反证：

控制 token 自身状态后，regime没有增量异质性。

---

## R3 — Liquidity regime

不是固定某一币liq，而是当时 universe 的 liquidity distribution：

- thin
- ordinary
- rich

例如目标池相对同期同链 cohort 的 percentile。

这比“时间=亚洲盘/美国盘”更有经济意义。

假设：

同一个 +10% momentum：

- thin-liquidity regime 右尾更凸，但死亡/假价更多；
- richer regime 成本后路径更稳定但倍数小。

下一验证：

比较同一 entry family 在 liquidity percentile 层的：

- PNL
- writeoff
- winner concentration
- remove-best-token

---

## R4 — Outcome-hazard regime

只能由**此前已经成熟的机会**形成，不能偷看当前token未来。

例如截至 t 已成熟的最近 N 个独立 token episode：

- dead/writeoff proportion
- positive proportion
- median cost-adjusted terminal result

形成：

`HOSTILE / MIXED / CONVEX`

这非常值得研究。

它回答的是：

> 最近这个市场是不是进入“一堆币快速死亡”的阶段？

假设：

HOSTILE regime 中：

- continuation-failure / fast exits 相对受益；
- long-runner / delayed confirmation 更差。

反证：

按前向成熟窗口构造后，HOSTILE标签对下一批token没有持续性。

---

## R5 — Data-quality regime

必须单独存在：

- fresh original-pool coverage
- median mark age
- provider coverage gap
- UNKNOWN rate

例如：

`DATA_GOOD / DATA_DEGRADED`

**DATA_DEGRADED 不应成为交易alpha。**

它的用途是：

- 限制结果解释；
- 判断某时段的策略结果是否可比较；
- 必要时减少依赖序列确认的研究策略，而不是把缺数据当静默。

---

# 四、完整赢家/输家路径：建议研究“形状”，不是再找参数

对每个独立 token/original-pool/episode，用已存前向路径归类。

## P1 — Immediate winner

entry后快速跨成本，并持续扩张。

研究问题：

是不是 breakout acceptance 仍然太慢，错过大量这种右尾？

若是，可以新设计：

**early impulse + immediate continuation**

但必须以实时连续帧确认，而不是未来峰值标签。

---

## P2 — False breakout

先跨成本附近甚至短暂盈利，随后迅速回落。

对应候选：

- continuation failure
- profit-budget
- activity-failure

下一验证：

比较它们是否减少左尾，同时没有显著砍掉 P1。

---

## P3 — Winner → giveback

曾实现明显净经济盈利，最后接近平/负。

这类路径上一轮已经确认真实存在。

新机制空间仍很大：

### Hypothesis A — Time-under-water after profit

一旦净经济利润曾达到X，不看固定峰值回撤，而看：

> 跌回峰值以下后持续多久未恢复。

这是与 profit-budget 不同的 **duration-of-giveback**。

自然验证：

同 entry，对比最终PNL和右尾截断。

---

## P4 — Slow grind winner

没有剧烈breakout，但逐步走高。

这可能是当前 fast-exit 最大的机会成本来源。

### Hypothesis B — Low-volatility economic progress

不是“价格平稳就持有”，而是：

- 单位时间净经济新高不断出现；
- drawdown小；
- liquidity/activity不恶化。

可作为 **持有而非入场** challenger。

反证：

资本占用过长且费后收益不高。

---

## P5 — Dead-on-arrival / rug-like

很快：

- liquidity collapse
- no economic exit
- writeoff
- price collapse

这类必须与普通失败分开。

研究目标不是用未来“rug”反填，而是寻找：

**入场后前30–120秒可观察的 hazard transition。**

例如：

- price↑但 liquidity连续恶化；
- 活跃高但 price无法前进；
- sequence 中断后恢复失败；
- buy-share高但经济值持续下跌。

现有exit已有其中几种，可以继续扩展“复合 hazard”但不要参数喷洒。

---

# 五、退出后5/15分钟标签：很有价值，但只能做研究标签

我支持新增：

`exit +5m`  
`exit +15m`

固定同原池结果标签。

必须分成：

- observed
- dead/writeoff
- unknown
- source/pool incomparable

用途不是重算过去最优退出，而是回答两个问题：

### Q1. 我们是不是普遍卖早了？

若某exit之后：

- +5m/+15m经常大涨；
- 且不是一两个mega-winner驱动；

则该exit存在 opportunity-cost。

### Q2. 我们是不是卖得还不够快？

若退出后继续大跌/死亡，则说明退出方向正确，甚至可能还太迟。

最重要的派生分类：

- `GOOD_ESCAPE`
- `EARLY_EXIT`
- `NEUTRAL`
- `LATE_EXIT`
- `POST_EXIT_UNKNOWN`

阈值必须预注册，并按token episode聚类。

**绝不能据此把历史exit重新移动到5分钟后/前。**

---

# 六、一个我认为目前特别值得新增的机制

## Exit regret-adaptive challenger — 但只允许前向版本

不是用上一笔未来结果直接在线改参数。

设计思路：

在某个策略版本开始前，冻结一个**只使用此前已成熟exit标签**的 regime：

例如最近20个独立已成熟exit：

- early-exit比例高 → `TREND_PERSISTENCE regime`
- good-escape比例高 → `FAST_DECAY regime`

然后新机会：

- 在 TREND_PERSISTENCE regime 使用更宽松持有 challenger；
- 在 FAST_DECAY regime 保持快速退出。

这实际上是：

**历史已经成熟的退出误差 → 下一批持有policy选择**

不是事后调当前仓。

优点：

- 完全前向；
- 不要求新API；
- 直接利用用户要求的exit+5/+15标签；
- 比固定UTC小时更接近真正市场状态。

最大反证：

regime自相关太弱，上一批exit结果不能预测下一批。

若如此就否定，不继续细分。

---

# 七、“不买”本身应成为独立机制

当前214里大量策略都在研究如何BUY。

但成本后8.33%回本带意味着：

**不交易低质量机会可能是最大的收益来源之一。**

我建议研究：

## Cost-band dead-zone abstention

当信号虽然满足旧entry，但：

- 最近序列位移小；
- activity足够但 price displacement无法跨成本；
- 或波动噪声远高于有效方向位移；

建立一个独立 control：

**NO-BUY / SHADOW outcome**

不是把原策略改严，而是增加一个“如果当时跳过会怎样”的严格前向 challenger。

最重要的是保留：

- skipped opportunity 5/15/60m outcomes
- missed winner
- avoided loser

这样可以真正回答：

> 少交易是否比早进快退更赚钱？

而不是只在成交样本里研究。

---

# 八、普通 / 失败 / Rug 对照必须再拆一层

上一轮四分类按60m return很好，但这一轮完整路径应增加：

1. **Ordinary-survivor**：普通回报，池仍健康  
2. **Economic loser**：可卖但跌  
3. **Liquidity death**：确认原池死亡/核销  
4. **Route/data unknown**：不可判  
5. **Boom-giveback**：曾跨明显净利润后最终失败  
6. **Boom-survivor**：右尾并保留收益  

这会比单纯：

`winner / ordinary / failure / crash`

更适合寻找退出机制。

---

# 九、不可辨识的机制

当前不要宣称能识别：

- “美国盘/亚洲盘本身有alpha”
- 真实独立buyer人数，仅凭地址/count不足
- buy/sell笔数对应真实资金净流
- Dex liquidity增长=LP注资
- 某个时段突然更容易rug的因果来源
- price impact后的真实可执行收益
- 当前RH持仓结果的真实regime表现——报价age/coverage仍太差
- exit后没有报价=退出正确

这些都应保持 UNKNOWN/解释限制。

---

# 十、优先级建议

我建议下一轮实际自然验证优先：

**A. Exit +5/+15 fixed labels**  
这是信息价值最高、实现成本最低的新研究层。

**B. Mature-outcome hazard regime**  
用此前成熟episode形成 hostile/convex状态，不使用UTC时间直接交易。

**C. Cost-band abstention Shadow/Paper control**  
研究“不买”相对“买后快退”。

**D. Profit giveback duration exit**  
区别于当前纯幅度profit-budget。

**E. Slow economic progress hold challenger**  
专门保护缓慢但持续的赢家。

**F. Regime-conditioned entry/exit 只在上述regime表现出前向重复性后再实现。**

不要现在直接生成：

- 24个小时×策略；
- weekday策略；
- 一堆5/10/15分钟参数克隆。

---

## 下一自然验证

每个新机制都按：

- 新deployment frontier
- unique token/original-pool/episode
- 同成本epoch
- chain/surface分层
- full denominator
- UNKNOWN/right-censored保留
- total / median / tail
- top1/top3
- remove-best-token
- paired baseline

评价。

时间/regime研究最重要的停止条件是：

> **如果同一状态机制跨至少两个独立日期不重复，而“小时”本身只有事后拟合价值，则禁止把时间做成策略。**

本轮首轮判断：**存在值得继续追的 regime/完整路径新机制，但目前可识别的是“市场状态→下一机会”的前向异质性，不是“几点钟→赚钱”的时间alpha。**
