[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-030700-OPEN-R2-STRATEGY_DISCOVERY-RESULT  
REPLY_TO: C2C-20260907-030700-OPEN-R2-STRATEGY_DISCOVERY  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: STRATEGY_DISCOVERY  
DISPOSITION: **REVISE_AND_NARROW / FIX_PENDING_PROVENANCE_BEFORE_DEPLOY / NO_ALPHA_CLAIM**  
SENSITIVE_DATA: NONE

本轮通过官方隧道只读 `E:\memeTrader`，未改代码、DB、Runtime，未跑全历史SQL。当前模型可核验为 **GPT-5.6 Sol**；具体reasoning档位不可核验，记 `UNKNOWN`。

实际读取：

- `ROUND2/R2_PROPOSALS.md`
- `ROUND2/PATH_AND_REGIME.md`
- `ROUND2/FOUNDATION_REVIEW.md`
- `ROUND2/R1_ADVERSARIAL_PORTFOLIO.md`
- 当前未部署 `store.py` diff：
  - `activate_chain_market_entry_post_observation`
  - `_settle_pending_market_entry_observation`
  - pending cash/capacity
  - pending held-watch原池
  - expiry
  - SELL gross/net修复
- `capital_entry.py` 的现存 `fast_stop_reclaim`
- 相关当前机制索引。

## 一、新证据改变了首轮优先级

PATH_AND_REGIME 已经直接反驳“更快退出通常更好”：

16个baseline/clock共同终结配对只有：

- 2改善
- 3恶化
- 11相同
- 合计 `+7.508U`
- median delta = 0

两个改善主要是避免后续5U全损；三个恶化则把慢小赢家提前卖成小亏。

更重要的是，5个最终亏损仓在+120秒时全部仍：

- 价格高于入场；
- reported liquidity高于入场；
- buy-share ≥ 0.5。

所以我首轮提出的“持续性/表面强势可以确认持有”的任何简单版本都应降级。

**当前最有信息量的问题已经从“还能识别什么好形态”转成：**

1. signal正确后，实际成交是不是已经太贵；
2. 哪些早退值得做、哪些是在杀右尾；
3. 部分兑现后的余仓应否重新证明自己；
4. 有限资本下，选谁比单纯“是否READY”更重要。

---

# 二、对根11项提案的交叉裁决

### 1. 成交追价预算
**KEEP / 第一优先级。**

这是最干净的新行为轴，而且与基础审查发现的旧主入口same-frame问题直接相关。

但建议冻结为**实验性veto**，不能变成新公共执行规则：

- Control：第一份合格post-decision原池receipt照买；
- Candidate：同receipt若相对冻结signal价上涨超过 **当前往返成本带8.333%**，本机会永久拒绝；
- veto只作用candidate；
- 不允许价格以后回落再补买；
- signal价必须来自 `fill_signal_snapshot_id/source_snapshot_id`，不能用position过去错误复用的`entry_signal_price_usd`。

8.333%来源于当前4%/4%合同，不是历史拟合最优值，因此可冻结。

**自然反证：** candidate省掉的小亏不足以覆盖其错失的右尾。

---

### 2. 缓慢稳定持有许可
**REVISE，不能独立做成宽泛新策略。**

它和现有 `progress_clock` 是直接反命题，最有信息量的设计不是另外造一套“slow hold”入口，而是：

> **只在progress_clock原本将退出的时刻随机/配对给一次有限延期资格。**

建议候选：

- 到180秒原clock会退出；
- 最近3个独立有效frame的**净经济值均不下降**；
- 原池liq均不低于该180秒窗口首帧的85%；
- 则candidate只获得**一次额外120秒**；
- control按原clock退出；
- 120秒后仍执行原exit/maxhold，不再次延期。

这样直接回答：clock是否在杀“慢但健康”的仓。

不要重新设计另一个完整slow-runner。

---

### 3. 活动边际响应耗尽
**MERGE / REVISE。**

当前提法 `Δprice/Δactivity` 容易被rolling m5窗口机械效应污染，难解释。

更可辨识的替代：

**`activity_without_price_progress_exit`**

连续3个相隔15–60秒有效frame：

- m5 trades 或 volume 至少连续不下降；
- 净经济值没有新高；
- buy-share连续下降，末帧 `<0.50`；
- price尚未要求明确下跌。

触发后下一帧exit。

它和旧 `activity_failure` 的区别清楚：

- 旧：活动↑但价格已经跌；
- 新：活动仍旺，但**边际价格进展先消失且交易方向恶化**。

不要再计算伪精确“活动弹性”。

---

### 4. 利润回吐持续时间
**DEFER。**

机制有意义，但目前 `profit_budget` 还几乎没有专属自然触发；再立即增加“幅度+持续时间”版本，信息增益低且容易变成参数喷洒。

先等现有profit-budget产生真实专属触发，再比较：

- instant/two-frame retrace
- time-persistent retrace

否则现在只是继续设计尚无分母的第二层退出。

---

### 5. 部分兑现后的runner重新资格
**KEEP / 高优先级。**

这是目前真正没被旧runner完整回答的问题。

建议冻结最小状态：

- **只有真实partial fill完成后**启动新epoch；
- fill时刻冻结：
  - residual economic value；
  - liq；
  - completed_at；
- 之后180秒内，若余仓经济值至少形成一次 `>= fill基准 + 1%原stake` 的新高，且liq保持≥fill时85%，标 `REQUALIFIED`；
- 否则180秒后下一有效原池frame退出；
- requalified后回到现有trailing/maxhold；
- old pre-harvest high全部清空，不拼接。

Control使用完全相同partial fill，但没有requalification deadline。

1% stake沿用现有progress-clock尺度，避免另找新阈值。

---

### 6. 卖笔扩张、价稳的分配风险
**MERGE到第3项，不要再注册第二个相近ID。**

它和“活动边际响应耗尽”实际都在研究：

> 活动还在，但买方对价格的控制力消失。

将buy-share向卖方翻转作为第3项的核心状态即可。

不要称distribution/whale selling，因为当前只有rolling count。

---

### 7. 双边可交易活动确认
**CONDITIONAL / 低优先级。**

“有SELL笔”并不证明我的5U可卖，也不证明协议没有sell restriction。

可以作为独立no-buy实验，但报告必须叫：

**two-sided observed activity**

而不是sellability。

建议不和首批3–4项竞争资源。

---

### 8. 下行冲击→修复入场
**REJECT AS NEW ID，复用 fast_stop_reclaim。**

当前代码已有真实不同状态：

- 必须存在clean自然hard stop；
- 60–600秒后；
- 连续新帧；
- 价格收回stop价×1.08及原entry×0.9；
- liq保留≥stop时80%。

根提案本质上与此高度重合。

除非新统计能提出**不依赖先前本策略真实stop**的全市场shock-repair机制，否则当前新增ID只是换名。

---

### 9. 双侧reserve扩张
**SHADOW_ONLY / 暂不Paper。**

只有在：

- 明确V2/CPMM/PumpSwap型池；
- 同原池；
- base/quote reserve字段真实覆盖；
- 时序稳定；

才有意义。

当前L0 `liquidity_usd`不够支撑它；CLMM也不能直接套。

先测coverage，缺值不等于未扩张。

---

### 10. 同时机会排序/机制分歧
**KEEP，但应合并成一个Auction实验框架。**

这是R1反方最有价值的意见。

不要同时做：

- top-K ranker
- consensus
- specialist
- FIFO
- hash
- mechanism vote

五六个账户。

第一版只需要**三臂**：

1. `FIFO_K`：冻结round内最早K；
2. `L0_RANK_K`：同冻结集合里按预注册L0 score取K；
3. `HASH_K`：确定性hash取K，作为无信息control。

相同round、相同K、相同5U、相同exit。

如果L0 rank连hash/FIFO都打不过，就能直接否定大量“选最好”工程。

Mechanism-consensus先作为score解释字段，不单独注册。

---

### 11. 跨池份额迁移/价差
**DEFER / 不应当前实现。**

当前observer会丢弃完整 `raw.pairs`，兄弟池覆盖又受provider返回集合影响。

在没有稳定“当时完整可见池集合”之前做份额迁移，会把provider覆盖变化误当市场份额变化。

这比缺一个新策略更危险。

---

# 三、我建议本轮真正冻结的4个优先新实验

不是11个全部做。

### A. Chase Budget
同signal、同第一合法receipt：

- control买；
- candidate若`receipt_price/signal_price - 1 > 8.333%`则永久skip；
- 无replay。

**回答：执行延迟吃掉多少edge。**

### B. Clock Grace
只在现有progress-clock会触发时：

- 三帧净经济值不降；
- liq≥窗口首帧85%；
- candidate获一次120秒grace；
- control退出。

**回答：早退是否系统截断慢赢家。**

### C. Post-Harvest Requalification
实际partial fill后才启动：

- 180秒；
- 新余仓经济高点需超过fill基准至少1%原stake；
- liq≥85%；
- 否则退出。

**回答：第一次兑现后runner是否值得继续占资本。**

### D. L0 Opportunity Auction
同round冻结候选集，只比较：

- FIFO K
- L0-rank K
- deterministic-hash K

**回答：214套复杂机制是否真的帮助有限资本选币。**

这4项的信息增量明显高于再做若干price/count形态。

---

# 四、未部署pending market entry diff：发现两个必须修复点

整体方向是对的：

- 新执行epoch独立于策略定义；
- pending最多8；
- enrollment时按arm独立现金做预留；
- pending进入held watch并带冻结原池；
- 90秒expiry；
- `decision < observed <= ingested <= recorded`；
- ≤15秒新鲜；
- 正价格、完整liq、原池匹配；
- receipt append-only KV；
- 旧definition JSON没有被diff改写；
- gross/net修复方向正确。

但部署前我认为有 **2个必须修正**。

## MUST-1：成交receipt没有成为position/fill的真实执行snapshot provenance

当前 `_settle_pending_market_entry_observation()` 收到真正后帧 `snapshot` 后，却调用：

`_project(... snapshot_id=int(intent["source_snapshot_id"]))`

也就是**仍把signal snapshot ID写进入场fill/position的entry snapshot字段**，同时用后帧price成交。

后续会形成：

- `entry_snapshot_id` 指向signal frame；
- `entry_execution_price_usd` 来自另一个真正receipt；
- 真正receipt只存在独立KV。

这会让以后仅按position/fill审计时错误理解“哪个snapshot成交”。

**最小修复：**
无需新表，但必须让现有fill/position能够直接引用真正receipt。若held接收点不写token_snapshot，则至少增加/复用已有JSON证据字段保存不可变receipt key/observed/recorded，并明确`entry_snapshot_id=signal_snapshot`；更优是给实际receipt一个现有snapshot记录ID再写入entry_snapshot_id。

不能留下一个字段名叫entry_snapshot但实际指signal而文档称成交snapshot。

## MUST-2：`INSERT OR IGNORE receipt` 后没有显式验证“本次就是第一receipt”

当前：

1. `INSERT OR IGNORE kv(receipt...)`
2. 不检查`changes()`
3. 直接继续project当前snapshot。

正常单事务路径多半不会出错，因为intent随后会filled；但合同声称的是：

> **first eligible receipt immutable**

代码应让这个不变量本身可证明，而不是依赖调用顺序。

**最小修复：**
- receipt insert成功才允许project；
- 若key已经存在，只能读取冻结receipt并停止，不允许当前更晚snapshot代替；
- projection/intent completion与receipt应在同一事务内维持原子性。

这样重启/重复callback也不会产生“KV保存第一帧、实际fill却来自第二帧”的理论歧义。

---

# 五、pending现金与expiry审查

这部分总体**通过**。

- enrollment统计当前`ready/retry` pending；
- 每arm从可用cash扣除其pending reservation；
- `max_pending_buy_intents`继续限制8；
- due执行会将过期BUY标`failed`；
- 随后重建 `_market_entry_pending_tokens`，因此过期释放watch和未来cash reservation；
- settle时 `_project...` 还会重新计算实际net flow/cash，避免强行透支。

需要报告一个边界：

> reservation是“策略arm级pending reservation”，不是系统级资金锁表。

如果同一个arm从其他独立入口同时成交，最终settler仍可能因为真实cash变化而skip。这是正确的“不借钱”行为，不应为了保持计划fill强行锁旧214。

---

# 六、gross/net修复审查

这部分我支持部署：

旧代码把 `sell_terms.net_usd` 填进 `gross`，fee=0时没有金额差，但非零fee时字段语义错误。

当前diff正确分开：

- `gross = gross_usd`
- `net = net_usd`
- fill/trade.gross = gross
- cashflow/proceeds/realized PNL = net
- amountful minimum_output作为gross
- `net_recovery_usd`继续作为net
- staged probe得到net

没有发现二次扣fee。

它是**账本字段语义修复**，不是alpha变化。旧历史不能倒改。

---

# 七、最终交叉结论

**根提案不要一次实现11项。**

我支持当前先收敛为：

1. Chase Budget
2. Clock Grace
3. Post-Harvest Requalification
4. L0 Opportunity Auction

`activity marginal decay + sell-side expansion` 合并为一个后续候选。

明确否决当前新增：

- shock-repair新ID：与`fast_stop_reclaim`重复；
- 跨池份额迁移：输入集合尚不稳定；
- profit-retrace-duration：现有profit-budget自己都尚无足够专属触发；
- mechanism consensus单独策略：先放进Auction分析，不再制造相关账户。

**未部署执行diff在修正“receipt provenance”和“first receipt insert必须控制fill”两个问题前，我不建议部署。**

除此以外，pending expiry、现金预留、原池watch、严格后观察以及gross/net修复方向成立；旧214定义/hashes没有必要修改或重置。

所有上述结论都是研究/工程裁决，**没有任何新alpha被证明**。
