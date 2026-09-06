[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-OPEN-R1-DATA_ENGINEERING-RESULT  
REPLY_TO: C2C-20260907-024100-OPEN-R1-DATA_ENGINEERING  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: DATA_ENGINEERING  
SENSITIVE_DATA: NONE  

**DISPOSITION: CONTINUE_OPEN_RESEARCH / TWO_CONCRETE_FOUNDATION_CORRECTIONS / NO_ALPHA_CLAIM**

模型：**GPT-5.6 Sol**。具体宿主 reasoning/thinking 档位没有可核验运行元数据，标记 **未知**，不声称切换到其他模型。

本轮实际只读了 `ROUND2/RESEARCH_REQUEST.md`、当前权威状态、Paper执行和BUY/SELL结算必要代码；没有重跑全历史扫描、没有修改代码/DB/Runtime。尝试用本机 `sqlite3 -readonly` 做一个极小top-profit查询，但工作区没有sqlite3 CLI，因此没有伪造“已查数据库”的结果。

## 1. 已证新问题：旧206与新8的“下一报价”因果合同不同

**事实来源：`store.py` 当前exit settlement。**

新8臂有：

`require_post_decision_observation=True`

所以除了quote/mark在trigger之后被收到、记录，还要求：

`post_observed_at > pending_recorded_at`

即**市场观察本身也发生在退出决策之后**。

旧206多数没有这个字段。对它们，generic market Paper仍允许：

- trigger先发生；
- 某报价实际上在trigger前已经observed；
- 但因transport/cache延迟在trigger后才recorded/received；
- 只要sequence、新鲜度等其他条件满足，就可能成为“next” fill。

### 影响

这不是上一轮新8的bug，而是**旧合同本来就较弱**。

因此：

> 旧206与新8的exit PNL不能直接视为具有相同next-available-quote语义。

极端情况下，旧策略可能使用一个trigger前已经存在的价格成交，从而让退出结果偏好或偏坏；方向取决于市场移动，不能假定只会虚高。

### 最小处理

**不建议为了本轮研究回头修改214个旧策略定义。**

建议：

- 历史/增量统计新增一个 execution-timing eligibility 标记；
- 对已有mark能够判定 `post_observed_at <= trigger_at` 的旧fill，单列 `LATE_RECEIPT_PREDECISION_OBSERVATION`；
- 不物理删除原交易；
- clean candidate comparison中与新严格臂分层。

今后新增策略继续采用新8的强语义即可。

### 下一自然验证

观察未来新增候选的：

`trigger_at < quote.observed_at <= quote.recorded_at <= fill`

覆盖率，并与旧策略实际late-receipt比例分开报告。

---

## 2. 已证账本字段语义缺陷：SELL `gross_usd` 当前实际写的是net

**事实来源：`paper_execution.py` + `store.py` SELL settlement。**

`sell_terms()`正确区分：

- `gross_usd` = 价格×数量×卖出滑点后的金额，**未扣额外fill fee**
- `net_usd` = gross − additional fee

但Store随后执行：

`gross = sell_execution["net_usd"]`

然后把这个值同时写入：

- fill `gross_usd`
- trade `gross_usd`
- `net_cash_flow_usd`

### 当前实际影响

当前执行设置：

`additional_fee_usd_each_fill = 0`

所以**当前数值上gross==net，对现阶段PNL没有影响**。

但如果用户以后把额外手续费设置成非0：

- cash/PnL仍按net扣费；
- `gross_usd`字段却也已经扣了fee；
- 后续研究若用`gross - net`还原费用，将错误得到0；
- 成本分解、费用归因以及不同cost epoch比较会失真。

这属于明确的数据字段语义缺陷，不是策略失败。

### 最小修复

普通market SELL：

- `trade/fill.gross_usd` 写 `sell_execution["gross_usd"]`
- `net_cash_flow_usd` 写 `sell_execution["net_usd"]`
- realized PNL继续用net。

无需新表/架构。

amount-specific路径应按其quote字段单独明确“minimum output before/after extra fee”的语义，不要机械套普通路径。

### 下一验证

一条非零额外fee的部分SELL即可验证：

`gross - fee = net_cash_flow`

并独立重算position realized PNL。

---

## 3. 另一成本边界：SELL fee在gross不足时会被截断

**事实来源：`paper_execution.sell_terms()`。**

当前：

`net_usd = max(0, gross - fee)`

如果未来用户设置固定每fill fee，而且某个严重亏损仓的卖出gross小于该fee：

- 实际函数不会产生负cash flow；
- 相当于只扣到0，不再支付剩余fee。

若“额外手续费”定义为真正每次成交都必须支付的固定成本，这会**低估极端尾部成本**。

当前fee=0，所以**当前无实际影响**。

### 最小裁决

这需要根代理先明确额外fee合同：

- 若fee只能从卖出proceeds中扣，当前实现成立；
- 若fee是账户无条件承担的交易成本，应允许net cash flow为负或单独扣账户现金。

在fee仍为0时，**不阻止当前Paper研究**。

---

## 4. 当前最大现实偏差不是4%算错，而是impact完全未建模

**事实来源：用户冻结合同 + `buy_terms/sell_terms`。**

普通Paper现在是：

- BUY：mark × (1+4%)
- SELL：mark × (1−4%)
- 原池最低1000U；
- 不计算当前5U/20U订单相对池储备造成的price impact。

这是用户明确接受的轻量Paper合同，**不能叫工程bug**。

但它会产生一个非常具体的研究偏差：

- 新8臂每笔5U；
- 大量旧策略20U；
- 同样是1000U附近的池，5U和20U对真实池的影响比例完全不同；
- 固定4%模型会使不同notional策略的“可执行性误差”不同。

所以新旧策略直接比较PNL时，除了策略机制，还混入了：

`order size / liquidity`

差异。

### 最小隔离

不需要改普通Paper，也不建议建立全池impact simulator。

只需在研究层始终同时报告：

`entry_notional / entry_liquidity`

例如分桶：

- <0.25%
- 0.25–0.5%
- 0.5–1%
- 1–2%
- >2%

阈值仅示意，最终根代理可用无参数化描述分位数。

### 假设/反证

**假设：**异常漂亮的轻量Paper收益可能更集中于高notional/liquidity比例的浅池。

**反证：**如果赢家在低ratio、较深池以及已有amount-specific quote子样本中仍保持，impact解释会变弱。

### 下一自然验证

对已有exact/amount-specific challenger能够覆盖的自然样本，仅做同期Paper mark回款 vs exact minimum-output差值，不回写原fill。

---

## 5. 数据覆盖缺口会制造“已关闭样本选择”，而不是直接制造盈利

**事实来源：`ROUND2/RESEARCH_REQUEST.md` 当前实测基线。**

当前：

- RH 78持仓币，73 coverage gap；
- RH quote age P95约718秒；
- SOL 132持仓币，77 data failure；
- SOL age P95约345秒。

而正常market exit要求约15秒内的新鲜原池mark。

所以很多仓位不是“策略决定继续持有”，而是：

> 当前没有足够新鲜的原池证据完成估值/退出。

### 影响

如果研究只看closed positions：

- coverage好的币更容易进入终结样本；
- coverage差的币更容易保持right-censored/open；
- closed-only PF/胜率/expectancy可能产生严重选择偏差。

这对Robinhood尤其明显。

### 最小处理

任何新策略结果必须同时报告：

- BUY
- closed
- open/right-censored
- stale/unvalued
- provider coverage gap
- chain

并禁止以“closed subset正收益”直接排名。

### 下一自然验证

当同一open仓恢复fresh原池mark时，继续自然估值/退出；**不能拿后来价格反填此前未知阶段**。

---

## 6. NULL/错池/cache问题：本轮没有发现需要重开的新反例

**事实来源：当前权威状态及上一轮代码收口。**

已确认并保留：

- NULL liquidity不能计成功；
- 负liq不能交易；
- 失败不刷新旧success时间；
- 兄弟池不能替代原持仓池；
- 新8 source切换断序列；
- duplicate/future/predecision observation已被新8拒绝。

本轮没有找到新的代码事实足以推翻这些已通过的修复。

因此**不建议再次审计这些路径或增加新防御层**。

---

# 7. “异常盈利”当前如何处理

当前权威只给出：

`profit_budget: 20 BUY / 16 terminal / realized +4.394U`

这个量级本身**不构成异常盈利证据**，样本也太小。

我本来试图做一次极小的token级top-PNL只读查询验证是否单token集中，但本机没有sqlite3 CLI，所以：

**当前token concentration未知。**

不能声称它分散，也不能声称它被单赢家主导。

### 下一自然验证

根代理的增量统计应先做：

- token/cohort聚类；
- best token contribution；
- remove-best-token；
- closed + open分母；
- execution timing quality。

只有通过后才值得讨论它是不是新机制线索。

---

# 8. 本轮对新机制研究最重要的数据工程原则

我不建议先制造更多复杂输入。当前最有价值的是把任何新候选绑定到以下最小事实：

`source observation → ingest → decision → strictly later market observation → Paper fill → held fresh original-pool observations → exit trigger → strictly later exit observation → net-cost PNL`

每条策略再增加：

- execution-contract epoch
- source/provider
- chain/pool
- notional/liquidity ratio
- stale/unknown exposure time
- engineering eligibility

这样新策略数量即使继续增加，也不会重新掉进“账户多=证据多”的坑。

---

## 结论

**不阻止继续新增严格前向小额Paper实验。**

但我认为有两项具体基础工作值得根代理优先最小处理：

1. **旧206的predecision-observed / postdecision-received fill只做统计隔离，不回改旧合同。**
2. **修正SELL gross/net字段语义，并明确非零固定fee大于卖出gross时的合同。**

另外两项必须作为研究解释边界：

- stale/coverage造成right-censoring；
- unmodeled impact使5U和20U Paper执行真实性不可直接同质比较。

它们都比继续微调entry阈值更可能解释“为什么某些收益看起来特别漂亮”。

**未发现要求停止214、初始化、覆盖旧策略或开启Live的理由；上述任何内容也不构成alpha证据。**

实际读取路径：

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/ROUND2/RESEARCH_REQUEST.md`
- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md`
- `src/memetrader/paper_execution.py`
- `src/memetrader/store.py`：market entry projection、market exit settlement/PNL必要段
- `AGENTS.md`

未修改任何代码、数据库或运行状态。
