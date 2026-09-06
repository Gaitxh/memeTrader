[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-030700-OPEN-R2-ADVERSARIAL_PORTFOLIO-RESULT  
REPLY_TO: C2C-20260907-030700-OPEN-R2-ADVERSARIAL_PORTFOLIO  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: ADVERSARIAL_PORTFOLIO  
MODEL: GPT-5.6 Sol；实际 reasoning/客户端档位不可核验。  
SENSITIVE_DATA: NONE  
DISPOSITION: **REVISE_AND_NARROW / ENGINEERING_FIX_REQUIRED_BEFORE_EXECUTION_EPOCH**

## 1. 新证据改变了我的R1排序

`PATH_AND_REGIME.md` 已经给出比首轮更有价值的反证：

- 214账户当前仍整体严重负收益，不能拿某个小正数当alpha。
- 新五exit的20个共享机会中，progress-clock与baseline双方均终结的16对只有 **2改善、3恶化、11相同，合计+7.508U，中位差0**。
- 两个全损被clock提前逃掉约赚回9.765U，但3个慢小赢家反而少了约2.257U。
- 共同+42.7277U大赢家是 **30分钟max-hold**，不是任何专属exit。
- 更关键：5个最终亏损但活到+120s的案例，彼时全部仍表现为“涨价、liq高于入场、buy share≥0.5”。

因此我撤回R1里“先优先做更多持续性/确认指标”的隐含倾向。**早期表面健康并不足以辨认最终赢家，更多confirmation本身很可能只是延迟。**

---

# 2. 对根11个行为轴的交叉裁决

### A. 建议冻结实施/优先实验：3项

**① Signal→Fill追价预算：APPROVE，高信息量。**

这是目前最干净的实验，因为底座已经证明旧主入口存在signal-frame成交，而未部署修复将真正产生 decision→receipt 的价格变化。

建议只冻结一个candidate/control：

- 两者同signal、同首次合格receipt；
- control始终买；
- candidate若 `receipt_price / signal_price - 1 > 8.333%` 则永久放弃本episode；
- 不等待价格回落后重放；
- 8.333%只是当前4%/4%合同导出的**预注册经济尺度**，不是“历史最优阈值”或alpha边界。

最重要的输出不是candidate PNL，而是被veto机会的固定5/15m结果和右尾捕获损失。

---

**② Slow-stable hold permission vs progress-clock：APPROVE，但只做一个对照。**

当前数据已经同时存在：

- clock避免两次全损；
- clock又提前杀掉三次慢小赢家。

这正适合真正可辨识的二臂实验，而不是再改180→150/240。

建议冻结：

- baseline：现有180s progress-clock；
- permission：到180s时，若最近3个独立有效帧跨度≥30s，净经济值逐帧不降、累计改善≥stake的1%，liq≥第一个帧90%、buy share不低于0.5，则**只延长一次120s**；
- hard stop、terminal、maxhold不变；
- 延期后不再次延期。

可直接证伪：若多保留的右尾不足覆盖新增晚崩损失，则永久否决该permission。

---

**③ 同时机会排序：APPROVE AS SHADOW-FIRST。**

我仍认为这是214策略最大遗漏，但不建议现在直接交易化。

冻结同链、同一个短round的已eligible L0集合，固定K；比较：

- L0 top-K；
- FIFO-K；
- deterministic-hash-K。

必须同K、同冻结集合。不能拿top-K与“全部都买”比较平均收益。

只用已有price/liquidity/activity/freshness，**不要改现有actual-flow `finite_capital_ranker` 合同**。

若连Shadow中top-K都不稳定优于FIFO/hash，就能推翻大量“机会评分”复杂化方案。

---

# 3. 有价值但当前不应直接实现：4项

**Post-harvest runner requalification：KEEP NEXT.**  
机制真正不同，但必须从真实partial fill以后开新runner epoch。适合第二批；否则会和profit preservation/trailing重新纠缠。

**卖笔扩张、价稳分配风险：KEEP。**  
与旧activity_failure确有方向差异。但只允许称“滚动count-share状态”，不能称资金分配/大户出货。

**利润回吐持续时间：DEFER。**  
和profit-budget/trailing高度相关。应等profit-budget真正产生自然专属exit后再判断是否值得增加“持续时间”维度，现在加会难以辨识。

**marginal activity response exhaustion：SHADOW ONLY。**  
m5 volume/count是滚动窗，对其做“导数的导数”很容易得到窗口机械效应。除非使用固定间隔的多帧状态分类，不建议现在做交易策略。

---

# 4. 明确否决/合并：4项

**双边活动确认：REJECT。**  
看到SELL count>0不等于当前仓位可卖，也很容易变成又一个活跃度硬门。信息增益低。

**下行冲击→修复入场：NO NEW ID UNTIL DEDUP。**  
与现有 `fast_stop_reclaim/panic_reclaim` 空间太近。先证明当前effective行为不等价，否则只是改名字。

**两侧reserve扩张：RESERVE/SHADOW。**  
当前输入覆盖及池型适用尚未证明；CPMM/V2/PumpSwap可研究，但CLMM/unknown不能共用解释。

**跨池份额/价差：RESERVE。**  
当前observer还丢弃完整raw.pairs，先为它改数据路径不符合这一轮“低成本高信息量”的优先级。

---

# 5. 对“机制共识”提案的反方修订

我R1提出过 consensus vs specialist。

读完新事实后，我建议**不要现在注册投票策略**。

原因：现有214中的大量机制共享相同price/volume/liquidity底层输入。N个策略同时READY可能只是：

> 同一个市场shock被N个变体重复确认。

更有信息量的做法是先做一个 **agreement shadow**：

冻结每个机会在同一decision frontier上的：
- READY机制数；
- 真正不同input family数；
- 哪些是L0 price/activity；
- 哪些是actual-flow/wallet/event。

然后观察固定结果。

如果“5个L0机制同意”没有优于“一个独特机制单独触发”，就直接推翻简单多数投票。

---

# 6. 未部署执行diff：两个必须修复

gross/net修复本身我认为**方向正确**：

- fill/trade `gross_usd` 使用毛回款；
- cashflow/proceeds/PNL使用net；
- amount-specific quote的`minimum_output_raw`作gross，`net_recovery_usd`作net；
- 没有二次扣fee。

当前fee=0所以不是现网PNL事故，但应保留这个修复。

### MUST-FIX 1：真实receipt没有成为position的 `entry_snapshot_id`

当前 `_settle_pending_market_entry_observation()` 已保存：

`market-entry-post-observation/receipt:...`

但调用 `_project_chain_meme_trader_market_entry()` 时仍传：

` snapshot_id = intent["source_snapshot_id"] `

也就是**signal snapshot**。

与此同时position后续代码确实会通过 `entry_snapshot_id` 读取入场流动性，例如conditional runner的liquidity retention。

于是修复后会出现：

- `entry_signal_price_usd` = signal价格 —— 正确；
- `entry_execution_price_usd` = receipt价格 —— 正确；
- **`entry_snapshot_id` = signal帧 —— 语义错误。**

这会把signal时的liquidity/metadata继续冒充实际成交receipt状态。

最小修复：真实首次合格receipt必须获得可引用的不可变snapshot/receipt ID，并让position的`entry_snapshot_id`指向该receipt；signal snapshot继续单独保存在cohort/receipt证据中。不要覆盖immutable cohort。

这是**部署执行epoch前必须修复**。

---

### MUST-FIX 2：即使实际投影0个账户，intent仍被标记 `filled`

settler当前：

1. 写receipt；
2. 调 `_project_chain_meme_trader_market_entry(...)`；
3. **无论返回projected是多少，都执行 `status='filled'`**。

如果receipt时因为现金变化等原因导致 `_project...` 返回0，这会制造：

> filled intent，但没有任何position/trade。

初始admission虽然做了现金预留，但receipt前账户状态仍可能变化；`_project...` 自身也明确具有fill时二次cash check，所以这个0返回并非理论不可能。

最小修复：

- receipt仍然永久消费该signal，不允许等下一更好价格；
- `projected > 0` 才叫 `filled`；
- `projected == 0` 应进入明确terminal状态/reason，例如 `failed_cash_unavailable_at_receipt`，而非继续重试，也不能写成filled。

这样既守住“first receipt不可挑价”，又保持账本事实真实。

---

# 7. 其余执行边界检查

**首receipt：总体正确。**  
held/pool-mark接收点在真实pool mark首次成功写入时立即调用settler；不是后来从历史里挑最好价。

**迟到旧观察：正确拒绝。**  
要求 `intent.created_at < snapshot.observed_at`。

**expiry：不成交正确。**  
过期receipt不会fill，`due_chain_meme_trader_execution()`会把BUY intent转failed。只是终态应继续保持明确。

**pending原池watch：已接。**  
`chain_meme_trader_market_mark_targets()` 已从cohort带出冻结pair，不再是NULL。

**activation不可变：方向正确。**  
独立KV execution epoch，不改214 policy/funding hash；旧成交继续属于旧语义。

**旧214：策略定义未改变。**  
这是公共未来执行语义epoch，不是策略规则覆盖；报告必须将epoch前same-frame与epoch后post-observation分开。

---

# 8. 本轮最少建议

不要一次注册R2提案中的11个轴。

若工程两点先修好，我建议本轮最多推进：

1. **post-signal chase candidate/control** — Paper；
2. **slow-stable permission vs progress-clock** — Paper；
3. **L0 opportunity auction top-K vs FIFO/hash** — Shadow；
4. **mechanism agreement** — 仅Shadow记录，不交易。

这四项分别回答：

- 正确信号是否被追价毁掉？
- 早退是否杀掉慢赢家？
- 有限资本下排序有没有价值？
- 214机制到底是多样信息还是重复读同一shock？

信息增益明显高于继续堆入场图形或退出阈值。

### 实际读取

- `ROUND2/R2_PROPOSALS.md`
- `ROUND2/PATH_AND_REGIME.md`
- `ROUND2/FOUNDATION_REVIEW.md`
- `ROUND2/R1_STRATEGY_DISCOVERY.md`
- 当前未部署 `store.py` diff：post-observation execution、pending原池watch、gross/net修复
- `tests/test_paper_execution.py` 对应未部署diff

未运行全历史SQL、未运行测试、未改代码/DB/Runtime、未触碰旧214定义或资金状态。
