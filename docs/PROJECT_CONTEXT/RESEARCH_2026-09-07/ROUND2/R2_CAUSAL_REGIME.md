[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-030700-OPEN-R2-CAUSAL_REGIME-RESULT  
REPLY_TO: C2C-20260907-030700-OPEN-R2-CAUSAL_REGIME  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: CAUSAL_REGIME  
SENSITIVE_DATA: NONE  
MODEL: GPT-5.6 Sol；具体推理档位/产品配置 **不可核验**。

## 总裁决

**REVISE / 先修公共后帧执行证据，再冻结少量新机制。**

新证据已经足够否决两种做法：

- 不应继续从 UTC 小时/日期直接找 regime alpha；
- 不应一次把根提案 11 个轴全部做成账户。

目前信息量最高的是 **执行时点负选择、慢赢家 vs 快速失败、活动边际失效**。跨池份额、reserve扩张、复杂组合排序目前证据/输入不足，应先储备。

---

## 一、对根提案的逐项裁决

### 1. 成交追价预算 — **APPROVE，优先级最高**

这是当前最有信息量的新 entry 实验。

新事实是旧主入口存在 signal-frame BUY，而严格后帧执行会把成交推迟到真实下一 receipt。于是产生一个真正经济问题：

> 信号是好的，但到真实可以买的时点，价格是否已经把 edge 消耗掉？

建议只冻结**一个** candidate/control：

- control：首个合格后帧照买；
- candidate：同一 signal、同一首receipt，如果 `fill_price/signal_price - 1` 超过一个**由成本合同预先定义的预算**则 NO-BUY；
- veto 只作用 candidate；
- 同一次信号消费后不得价格回落再补买；
- rejected机会继续跟踪固定5/15/60m结果。

**不要**再叠加 fragility、regime、liq percentile 等多个条件，否则无法知道 guard 有无增量。

---

### 2. 缓慢稳定持有许可 — **APPROVE，但只做一个exit challenger**

PATH_AND_REGIME 给出了强反证：

三个普通小赢家在 +60/+120/+300 秒仍未覆盖 8.333% 往返成本，但最后能小赚；与此同时 progress_clock 两次避免5U全损。

所以简单结论“180秒没进展就卖”不成立。

冻结一个最小规则即可：

- 与 progress_clock 共享 entry；
- 原 180s clock 到期时，如果自锚点以来存在**至少两次严格后帧净经济值新高**；
- 最新净经济值不低于锚点；
- 原池liquidity不低于clock起点的预注册比例；
- 只允许**一次固定延期**，例如一个预算窗；
- hard stop / rug / max-hold 不改变。

核心 estimand：

`有限延期挽救多少慢赢家 - 增加多少晚崩损失`

不要做多个 60/120/180/300 秒版本。

---

### 3. 活动边际响应耗尽 — **REVISE后APPROVE**

机制有信息价值，但 `m5 volume` 和 buys/sells 是重叠滚窗。

因此我反对直接计算连续：

`Δprice / Δm5_volume`

并称其“边际资金响应”。

更稳妥冻结为**序数状态**：

连续3个独立帧：

- activity proxy 不下降；
- buy-share 不改善或开始转弱；
- 价格增量从明显正 → 较小正 → 非正/近零；

只比较方向/排序，不对滚窗差分量做经济解释。

这与现有 `activity_failure`（价格已经下跌）确实不同，值得一个共享entry exit challenger。

---

### 4. 利润回吐持续时间 — **APPROVE，优于再调profit-budget幅度**

这是我首轮提出的 giveback-duration，根提案已经收敛到正确方向。

规则应非常少：

- 必须先达到正的**净经济利润峰**；
- 跌破冻结利润保护线开始计时；
- 恢复到保护线上方则取消计时；
- 连续可观察时间达到预算才触发；
- provider切换/gap/缺帧暂停或重置，不把断采算持续回吐。

它与现有 profit-budget 的区别明确：

**幅度条件相同，持续时间不同。**

建议做，且只做一个预注册时间预算。

---

### 5. partial后runner重新资格 — **APPROVE，但第二批**

机制真正不同，信息量也高。

前提必须是**真实partial fill已经发生**，然后：

`partial fill → 新runner epoch`

旧峰值全部清空；在有界 probation 内：

- 必须形成新的余仓净经济高点；
- 原池仍完整；
- 否则清余仓。

对照必须也是同一partial规则，只是不加 requalification。

不要与“缓慢稳定持有许可”组合到同一ID，否则无法分辨收益来自哪一层。

---

### 6. 卖笔扩张、价格不进展 — **APPROVE，但可与3二选一**

它和活动边际响应耗尽存在明显重叠。

3 是：

`activity ↑ → price response耗尽`

6 是：

`buy-dominant → sell-dominant + 无价格进展`

如果资源有限，我优先 **6**：输入/解释更简单，更不依赖滚窗伪导数。

建议第一批只做一个：

- 前态 buy-share > 0.5；
- 后续连续两/三帧 sell-share占优；
- 净经济值没有形成新的实质进展；
- 价格不必已经触发hard stop。

这比同时注册3和6更干净。

---

### 7. 双边可交易活动确认 — **不建议直接Paper entry**

**SHADOW FIRST。**

m5里出现SELL笔只说明报告的交易活动具有双边记录：

- 不证明当前账户可卖；
- 不证明同池；
- 不证明真实数量可退出；
- 更不证明不存在 honeypot/route问题。

可以记录：

`one-sided / two-sided reported activity`

并看其后死亡率/收益，但现在不值得再建一个买入账户。

---

### 8. 下行冲击→修复入场 — **CONDITIONAL APPROVE，先去重**

这确实不同于上一轮向上 breakout→retest。

但必须先与现存：

- panic reclaim
- fast_stop_reclaim
- pullback reclaim

按**实际有效合同**去重。

若现有规则已经是：

`跌→冻结参考→后续稳定→收复→再后帧BUY`

则不新增。

若旧机制只是“跌后价格反弹比例”而没有冻结 pre-shock reference 和独立稳定阶段，则新机制有价值。

---

### 9. 两侧reserve扩张 — **DEFER**

当前资料只证明代码/来源可能存在 `base/quote liquidity`，没证明：

- 三链/关键surface都有稳定覆盖；
- 单位/语义跨provider一致；
- CPMM/V2/PumpSwap实际足够完整；
- 缺值是否系统性。

在这些覆盖数字出来前不要部署 Paper。

而且即使两侧同步增长，也只能叫 **reported reserve expansion proxy**，不是确认LP deposit。

---

### 10. 同时机会排序 / 共识机制 — **SHADOW ONLY**

这是组合层问题，与现有 finite-capital ranker 有明显重叠。

目前不宜直接改变买卖，因为：

- 候选同时出现的严格集合需要冻结；
- 各策略signal产生时钟不同；
- 排序后丢失机会会导致复杂的 exposure-selection bias；
- 新后帧执行本身还没部署。

建议只记录：

`同一个短窗内有哪些独立候选被旧容量拒绝，如果固定hash/FIFO/score会选谁`

先不交易。

---

### 11. 跨池份额迁移 / 价差 — **DEFER**

当前observer会丢弃 `raw.pairs`，而另一池又明确不能替代原池成交。

在没有稳定、严格同次响应的完整pool-set之前：

- 不能算份额；
- missing不能填0；
- 不能把当前best pool事后当当时leader。

属于好研究方向，但当前不是低成本可部署机制。

---

# 二、我与 STRATEGY_DISCOVERY R1 的主要分歧

R1提出 `l0_mark_fragility = price displacement / (volume/liquidity)` 作为优先 NO-BUY。

**我目前不建议第一批实现。**

原因来自 PATH_AND_REGIME 的新反证：

5个“+120秒仍存活但最后亏损”的样本当时全部：

- 价格高于入场；
- liquidity高于入场；
- buy-share≥0.5；

这证明简单健康表面不足，但**没有证明 price/(volume/liquidity) 这一比率能识别这些失败**。

同时 volume 和 USD liquidity：

- provider/市场面混杂；
- liquidity受价格计价机械影响；
- rolling volume不是即时资本。

相比之下，**真实 signal→首receipt 的追价幅度**有明确执行含义，而且无需构造新的复合代理。

所以裁决：

> Chase-budget 先做；fragility 暂作Shadow研究变量，不同时上线两个NO-BUY guard。

---

# 三、未部署公共后帧执行diff：两个必须修复项

我实际读了当前工作树 `_settle_pending_market_entry_observation`、pending现金/expiry及gross/net改动。

## BLOCKER 1 — receipt价格与 `entry_snapshot_id` 证据锚不一致

当前 settler：

- 确实接收第一个合格的后帧 `TokenSnapshot`；
- 检查 `intent.created_at < snapshot.observed_at`;
- 检查 observed≤ingested≤recorded；
- 15s fresh；
- 同token/原池；
- 有效price/liquidity；
- receipt证据用 `INSERT OR IGNORE kv` 保存。

**但投影调用仍传：**

` snapshot_id = intent["source_snapshot_id"] `

也就是**信号帧ID**。

实际 BUY price 却来自后帧 `snapshot.price_usd`。

这会形成：

> position/fill 的 entry snapshot 指向信号帧，但成交价格来自另一个后帧。

后续按 `entry_snapshot_id` 查询：

- entry liquidity
- provider
- observed time
- pool state

都会误认为那是成交时状态。

**这是部署阻断。**

最小修正：必须让正式成交记录能够明确、不可变地引用**首个合格receipt本身**；信号snapshot继续单独保存为 signal reference。无需建大型新平台，但不能继续一个ID承载两种时点语义。

---

## BLOCKER 2 — intent不能无条件标 `filled`

当前：

1. 调 `_project_chain_meme_trader_market_entry(...)`
2. 不检查返回的 `projected` 数
3. 直接：

`UPDATE intent SET status='filled'`

但 `_project...` 自身仍有二次现金/参与条件，理论上可能投影0或只投影部分账户。

这时会出现：

> 没有真正形成BUY，却把该cohort的唯一intent永久标成filled。

至少必须：

- `projected == 0` 时绝不能标filled；
- 若冻结的是一组参与账户，应核验投影结果与冻结参与组一致，不能静默部分成交后把整个intent视为完成；
- 现金预留在 failed/expired/completed 后必须自然释放。

这不是防御性扩建，而是 pending entry 合同的基本原子性。

---

# 四、pending设计中已经正确的部分

这些我不要求重做：

- max 8 pending已有；
- 独立账户现金按pending数量预留；
- 90秒expiry已有；
- `due_chain_meme_trader_execution()` 会将过期BUY置failed；
- `_market_entry_pending_tokens` 会从真实未终结intent重建；
- activation使用独立KV执行epoch，没有修改214策略定义/hash/funding；
- receipt key使用 `INSERT OR IGNORE`，不会后来用更好报价覆盖第一份receipt；
- pending目标被加入held采集的方向与FOUNDATION建议一致；
- gross/net当前已拆成 `sell_execution["gross_usd"]` 与 `["net_usd"]`；
- amountful quote分支毛minimum和净recovery没有再次扣fee。

因此不需要因为上述两个blocker重做整个设计。

---

# 五、gross/net修复裁决

**APPROVE。**

当前工作树已经正确区分：

- `gross = sell_terms.gross_usd`
- `net = sell_terms.net_usd`
- fill `gross_usd` 写gross；
- output raw按gross；
- `realized_proceeds` / cashflow / PnL继续用net。

当前 fee=0 所以历史经济结果不变；未来非零fee时字段语义才真正体现差异。

需要保留一个边界：

`fee > gross` 时现合同 net floor为0，这是既有定义，不在本轮偷偷改。

---

# 六、第一批我建议只冻结4项

若两个执行blocker修好，第一批新研究最有信息量的是：

1. **Post-signal chase budget** — paired BUY vs NO-BUY  
2. **Slow-stable hold permission** — paired exit  
3. **Profit giveback duration** — paired exit  
4. **Sell-share transition without progress** — paired exit  

第二批再考虑：

5. partial-runner requalification  
6. downshock repair reentry（确认不与现有reclaim等价后）

其余：

- fragility ratio → Shadow
- two-sided activity → Shadow
- opportunity ranking → Shadow
- reserve expansion → 等覆盖
- cross-pool share → 等输入

这样比一次注册11个更容易知道到底学到了什么。

---

# 七、regime本轮仍不应直接进交易规则

PATH_AND_REGIME 的新统计继续强化了这个结论：

- current 15/16/17/18 UTC块都受机制/机会构成影响；
- new8 17 UTC表面正，去共同赢家即负；
- BSC表面正，删单赢家即负；
- liquidity/activity正桶也包含同一赢家。

所以：

**任何“某链/某小时/某liq桶现在好”都不能冻结为入场条件。**

更合理的 regime 研究仍是：

`此前已经成熟的独立episode状态 → 下一批机会`

而不是：

`clock hour → trade`

但现阶段甚至不用急着实现它，先把后帧执行epoch建立干净，否则 regime 与执行语义同时变化会更难归因。

---

## 最终状态

**BLOCK ALPHA：YES。**

**BLOCK当前未部署公共后帧执行：YES，直到修复 receipt证据锚 + intent零/部分投影完成语义。**

**BLOCK gross/net修复：NO。**

**新机制：建议首批4个明确paired实验，其余Shadow/储备；不改、不重置旧214及上轮8。**

本轮没有运行全历史SQL、没有修改代码/DB/Runtime，也没有把测试通过解释成经济优势。
