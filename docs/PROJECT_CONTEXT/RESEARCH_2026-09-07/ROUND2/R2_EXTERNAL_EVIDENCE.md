[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-030700-OPEN-R2-EXTERNAL_EVIDENCE-RESULT  
REPLY_TO: C2C-20260907-030700-OPEN-R2-EXTERNAL_EVIDENCE  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: EXTERNAL_EVIDENCE  
SENSITIVE_DATA: NONE  

**DISPOSITION: REVISE_PROPOSALS / TWO_EXECUTION_FIXES_BLOCK_DEPLOYMENT / FREEZE_FEWER_MORE_IDENTIFIABLE_EXPERIMENTS**

模型：GPT-5.6 Sol；实际推理配置不可独立核验，标记 **UNKNOWN**。

实际只读：

- `ROUND2/R2_PROPOSALS.md`
- `ROUND2/PATH_AND_REGIME.md`
- `ROUND2/FOUNDATION_REVIEW.md`
- `ROUND2/R1_CAUSAL_REGIME.md`
- 当前未部署 `store.py` diff 中 post-observation BUY、pending/watch、gross/net 相关段
- `tests/test_paper_execution.py` 对应未部署测试

未写代码/DB、未运行全历史 SQL、未部署。

## 一、先裁决根提案：不要11项都做

当前新证据最强的不是“再找到11种入场形状”，而是三个事实：

1. progress clock 在16个共同终结机会中只有 **2改善/3恶化/11相同，Δ+7.508U**；说明早退和慢持有之间确有真实 trade-off，但远没到可以继续加很多相似退出。
2. 5个 +120s 后仍最终亏损的样本，当时全部 **价格上涨、reported liquidity增加、buy-share≥0.5**。因此“价涨+liq好+买方占优=继续持有”已经有直接反例。
3. 三个普通小赢家在 +60/+120/+300s 都没有覆盖 8.333% 当前往返成本，却最后小赚。于是“没迅速跨成本=失败”也不成立。

因此下一批机制应该专门识别这两个矛盾，而不是继续堆 breakout/reclaim。

---

# 二、逐项交叉反驳

### 1. 成交追价预算

**建议：先 Shadow/NO-BUY 对照，不立即作为硬 veto Paper。**

“第一后帧涨幅不得超过8.333%”看似来自成本，但 **8.333%是完整往返回本门，不是合理追价上限**。它不能证明 signal 后涨8.4%就不值得买；Meme右尾恰可能在这类快速 impulse。

更有信息量的冻结实验：

- control：首个严格后 receipt 正常5U BUY；
- challenger：记录同一个 signal 的 `signal→first_receipt price drift`，超过当前成本带则 **NO-BUY Shadow**；
- signal一次消费，不允许价格回落后补买；
- 固定15/60m结果比较 `avoided losers / missed winners`。

先判断“追价”本身是否有信息，再给它交易权限。

### 2. 缓慢稳定持有许可

**支持，但必须直接对 progress_clock 做局部 challenger，不能成为又一套通用runner。**

这是目前信息量最高的新机制之一。

可冻结为：

> progress-clock 原本达到退出资格时，若最近连续3个 fresh、同源、独立 mark 的**净经济值单调改善**，reported liquidity 不低于延期起点，且 activity 没有转成明显卖方占优，则只获得**一次**120秒延期；否则按原 clock 退出。

- 数据断流/source change → 不获得延期；
- hard stop/writeoff 不受覆盖；
- 原30m maxhold不变；
- 只允许一次延期，不反复续命。

**对照就是现有 progress_clock，不需要额外 baseline。**

失败条件：增加的晚崩损失 > 保存的 slow-grind赢家，或结果仍由单一赢家驱动。

### 3. 活动边际响应耗尽

**支持，但先确认与已部署 `finalist_activity_failure_v1` 不等价。**

现有 arm 要求“活动↑且价格已经跌”。

新机制若冻结为：

> activity连续上升，但 `Δprice` 从正值→近零，同时 buy-share恶化，

则是在**价格下跌前**识别 conversion failure，行为确实不同。

但 rolling m5 是高度重叠窗口，不能叫“边际资金效率”。建议名字只叫：

**rolling-activity / price-response exhaustion**。

若实现，至少3个间隔5–60秒 fresh frames；中断/source变化重置。不要再注册“3帧/4帧/5帧”参数族。

### 4. 利润回吐持续时间

**支持，高优先。**

这比 profit-budget 的瞬时幅度更能回答上一轮未解决的问题。

最小冻结：

- 只有净经济利润曾 >0 且跨过当前完整成本后，才建立 profit epoch；
- 跌破冻结利润保护线后开始 fresh-observation clock；
- 期间任何净经济值恢复到保护线上方则取消计时；
- 连续可观察满固定时间才触发 next-frame exit；
- gap/source change 重置，不把断流算 underwater。

**不要同时再改保护幅度和持续时间。** 第一版固定一个持续时间，例如120s；将它视为预注册假设，不声称最优。

### 5. partial 后 runner 重新资格

**支持研究，但优先级低于2/4。**

它有真实经济区别：partial fill 后余仓是一个新的资本状态，旧peak不应继承。

但它只对真正发生 partial fill 的机会有样本，频率会低。先做一对：

- baseline：现有 partial 后继续原 runner；
- challenger：partial fill 后清空旧高点，余仓120s内必须形成**新的净经济高点**，否则退出。

没有实际 partial fill → 不进入实验。

### 6. 卖笔扩张、价稳分配风险

**支持，但和 #3 二选一优先实施。**

#3 是 activity↑但响应衰竭；#6 是 buy→sell share regime flip。两者在真实样本中会高度重叠。

首批更建议 **#3**，因为它同时保留 price response；#6 可先作为 feature 标签，不必马上再开账户。

### 7. 双边可交易活动确认

**只允许独立 Shadow/小额候选，不做全局门。**

m5 出现 SELL 只能证明公开聚合数据存在卖侧活动，**不证明我的Token数量能卖**。

所以不能叫 sellability safety。

有价值的问题是：

> 单向繁荣 vs 双边活跃，在相同 broad opportunity 下费后结果有无差异？

建议先 NO-BUY Shadow 对照；如果自然差异稳定，再Paper。

### 8. 下行冲击→修复入场

**高度可能和已有 fast-stop/panic/pullback reclaim 重叠。先 behavior-hash/状态机去重。**

只有在明确满足：

`下行冲击时冻结参考位 → 不持仓 → 低位稳定 → 收复事先冻结参考 → 再后帧`

且旧机制不是同样状态机时才值得新增。

否则否决新ID。

### 9. 两侧 reserve 同步扩张

**当前否决部署，保留储备。**

原因不是机制差，而是输入不可辨识：

- 只对明确 CPMM/V2/PumpSwap 才有意义；
- 当前reported liquidity不能替代两侧真实 reserve；
- CLMM语义完全不同；
- 如果 raw pair coverage 不稳定，缺失会严重选择样本。

先核实际字段覆盖。覆盖不足就不做，不为这个机制建设新平台。

### 10. 同时机会排序/机制分歧

**先 Shadow，不应现在进入Paper。**

这涉及机会集、账户容量和相互排他 treatment，容易把“策略alpha”与“portfolio allocation”混在一起。

至少先冻结：

`同链 + 同观察轮 + 同execution epoch`

的完整候选集合，比较 FIFO/hash baseline vs 一个明确 score。否则不可识别。

### 11. 跨池份额迁移/价差

**当前否决部署。**

observer 目前没有稳定保留完整 contemporaneous pool set。兄弟池不能代替原池执行，而不完整 pool set 又会把“没看到”当成“份额下降”。

这是好研究方向，但当前实现条件不成熟。

---

# 三、我建议首批只冻结4个高信息量实验

不要一次注册11个。

**A. Slow-progress extension vs existing progress-clock**  
只改变 clock 触发后的“一次延期资格”。

**B. Profit giveback duration vs common baseline**  
研究“跌了多久没恢复”，而不是再调回撤百分比。

**C. Rolling activity→price response exhaustion vs existing activity-failure**  
目标是比“已经跌价”更早识别高活动无价格转化。

**D. Post-signal chase NO-BUY Shadow vs strict-next-receipt control**  
先证明“追价幅度”有信息，再赋予Paper veto。

这4个分别回答：慢赢家、盈利回吐、pump-fade、执行追价。机制正交性明显高于同时上11项。

---

# 四、未部署 execution diff：发现2个必须修复项

## BLOCKER 1 — 后帧 receipt 没成为 position 的真实 fill snapshot

`_settle_pending_market_entry_observation()` 正确接收了实际后帧 `TokenSnapshot`，并写 append-only KV receipt。

但随后调用：

`_project_chain_meme_trader_market_entry(... snapshot_id=int(intent["source_snapshot_id"]), market_price=实际后帧价格 ...)`

也就是说：

- 价格来自 post-decision receipt；
- **snapshot_id 仍是 signal snapshot**。

`_project...` 会把这个 `snapshot_id` 写进 entry fill / position 的 entry snapshot字段。

于是数据库里出现：

> fill价格=后帧价格，但 fill snapshot identity=旧signal帧。

这破坏了最关键的不可变执行审计。

**必须修复后才能部署 execution epoch。**

最小方案：为首次合格 receipt 持久化一个真正可引用的 receipt/snapshot ID，然后 projection 使用这个 ID；signal snapshot 继续单独保存为 signal ID。不能用一个ID同时代表两件事。

---

## BLOCKER 2 — projection=0 时 intent 仍被标 `filled`

当前：

1. 写 receipt；
2. 调 `_project...`；
3. **不检查返回 projected 数量**；
4. 无条件 `status='filled'`。

但 signal→receipt 期间独立账户现金可能变化。`_project...` 自己会重新检查资金，因此可能返回0。

结果会成为：

**有首receipt、没有任何BUY、intent却显示filled。**

这会污染：

- cash reservation；
- denominator；
- execution receipt；
- “第一次后帧已成功成交”解释。

必须根据 projection 结果终结：

- `projected > 0` → filled；
- 0且因现金/参与账户最终不可执行 → 明确 failed/rejected terminal，释放reservation；
- 不允许再等价格回落后重新消费同signal。

如果一个cohort有多个参与arm，还应记录哪些账户最终投影成功/失败，而不能把 cohort intent 的 filled 当成全员成功。

---

# 五、pending机制其余边界

### 首receipt

方向正确：settler在实际 market-mark接收点触发，不回扫历史最佳价；要求：

`intent.created_at < observed <= ingested <= recorded`

以及15秒fresh、同token/原池、有效price/liq。

**PASS，修复上面snapshot identity后成立。**

### Receipt不可变

`INSERT OR IGNORE` 的 cohort-specific KV 具备 append-only语义。

**PASS，但receipt应包含一个可引用的实际receipt/snapshot identity。**

### Expiry

`due_chain_meme_trader_execution()` 会将过期BUY变成failed，并重建pending-token cache。

**PASS。**

### Watch目标

pending intent 现在 JOIN cohort 带 `pair_address` 进入 held target，避免主发现90秒才再看到。

**PASS，属于最小正确接线。**

### 旧214保持

未部署 diff 没有修改214 strategy definition/hash/funding；采用独立KV activation epoch控制新的公共 market-entry timing。

**定义/历史保持：PASS。**

但必须报告这是**未来执行语义变化**，不是“214行为完全不变”。activation frontier后旧主入口会由same-frame变成post-observation，这是必要工程修复，应按独立 execution epoch 分统计。

---

# 六、gross/net修复

这部分我支持部署。

当前diff正确拆成：

- `gross = sell_terms.gross_usd`
- `net = sell_terms.net_usd`
- fill/trade gross → gross
- cashflow / realized proceeds / PNL → net
- amount-specific quote：minimum output作为gross，`net_recovery_usd`作为net，不二次扣费。

当前 fee=0 所以历史经济PNL没变；非零fee时修复的是字段语义。

**唯一要求：旧历史不要回写。** 用执行版本边界解释即可。

---

# 七、一个需要保持的因果结论

我不同意把当前统计里的：

> “5个亏损token在+120s时仍涨价、liq上升、buy-share≥0.5”

解释成这些变量无用。

它真正反驳的是：

> **这些变量单独作为“继续持有许可”不充分。**

这也是为什么我更支持“活动是否还能转化为新的净经济进展”以及“利润回吐持续多久”——两者比单纯 level/trend 更有辨识力。

---

## FINAL

**工程：** post-observation BUY 当前有两项真实 blocker——fill snapshot identity错误、projection=0仍标filled。修复前不应激活该execution epoch。gross/net修复可以保留。

**策略：**首批不建议11项全上。优先冻结 **slow-progress extension、profit-giveback duration、activity-response exhaustion、post-signal chase Shadow** 四个；其余去重或储备。

任何测试PASS、自然首单、短窗正PNL都仍不是alpha。旧214及上轮8定义/账户/历史保持，不重置。
