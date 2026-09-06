[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-030700-OPEN-R2-CHAIN_MICROSTRUCTURE-RESULT  
REPLY_TO: C2C-20260907-030700-OPEN-R2-CHAIN_MICROSTRUCTURE  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: CHAIN_MICROSTRUCTURE  
SENSITIVE_DATA: NONE  
MODEL_STATUS: **未知；项目侧无法核验实际模型/推理档位。**

## 总裁决

根提案这轮已有明显实质增量，但我建议继续**删重而不是扩张**。当前最值得冻结的研究问题集中在：

1. **signal→真正后帧时 edge 被吃掉多少；**
2. **活动继续增加却不再产生价格进展；**
3. **慢速、小幅但持续的经济进展何时值得延长持仓；**
4. **第一波后卖方活动逐步占优但价格尚未崩时是否应释放资本。**

Reserve / 多池方向仍值得研究，但当前数据保留链路还不够干净，暂不应比上述四项更早部署。

同时，未部署的公共 pending BUY 修复存在 **1个权限/合同级阻断 + 1个证据语义缺口**，gross/net 修复方向正确。

---

# 一、对根11轴逐项交叉裁决

### 1. 成交追价预算
**APPROVE，优先级A。**

这是目前最可辨识的新 entry treatment，因为它研究的不是“哪个币会涨”，而是：

> 已冻结信号到真正合法后帧之间，成本后机会是否已经被市场吃掉。

`PATH_AND_REGIME` 已证明旧主入口存在 signal-frame BUY，而新8严格后帧；因此这是直接影响经济真实性的行为轴。

### 可冻结最小规则
不要历史优化阈值。第一版只比较：

- control：合法第一后帧照买；
- candidate：若 `P_fill / P_signal - 1` 已超过**当前一侧BUY摩擦4%**则拒绝。

我不建议第一版直接用8.33%往返带。因为8.33%是从signal价到未来卖出回本的总要求，而这里研究的是**仅入场等待造成的额外追价**；用4%作为“额外又吃掉一份买侧成本预算”解释更清楚。

如果根想用8.33%，也可以作为另一个预注册设计，但不要同时注册4/6/8.33/10%四个版本。

**必要control：同signal、同slot/cash admission，candidate veto不得取消control。拒绝后该signal永久consumed，不能等回落再补买。**

---

### 2. 缓慢稳定持有许可
**APPROVE，但必须对 progress_clock 做“许可overlay”，不是另造独立趋势entry。**

新证据非常关键：

- clock只2次明显改善；
- 3次提前卖掉后来小赢家；
- 三个普通赢家 +60/+120/+300s 仍没覆盖8.33%往返成本。

所以“180秒没进展就走”确实过于粗糙。

### 最小冻结规则
我建议不要复杂成多变量score。

在 `progress_clock` 本来要退出时，只允许**一次**延期，例如180秒：

必须同时：

- 从上一个 progress anchor 至今，净经济值没有下降超过 `0.5% stake`；
- 最近两份有效独立mark的价格非递减；
- 原池liquidity均 ≥ 该position入场liq的85%；
- 最近一帧 buy share ≥ 0.5；
- 数据连续、新鲜、同source；断流不触发许可；
- 每仓一生只延期一次。

然后继续原 hard stop / trailing / maxhold。

这里的数值应标**设计值，不是历史最优**。

**对照：原 progress_clock，不是 baseline maxhold。**

---

### 3. 活动边际响应耗尽
**APPROVE，但与旧 `finalist_activity_failure_v1` 必须明确分离。**

旧activity_failure要求：

`price↓ + economic value↓ + buy share↑ + volume↑`

新机制应冻结为**price尚未跌之前的 exhaustion warning**：

三份独立有效帧：

- rolling m5 activity 连续上升；
- 前一段 price increment >0；
- 后一段 price increment ≤约0；
- buy share同时下降，或sell share上升。

不能计算“新增volume”；rolling 5m相邻值重叠，只能称**窗口状态变化**。

### 更有信息量的替代
不要用比例 `Δprice/Δvolume`，会对微小分母极不稳定。

直接做序列分类：

`activity ↑↑ + price progress + → flat + buy-share ↓`

再下一独立帧触发退出。

这与旧activity_failure的“已经跌了才认错”形成真正早一阶段的对照。

---

### 4. 利润回吐持续时间
**DEFER / 低于上面三项。**

它和现有：

- trailing
- profit_budget
- progress_clock

都高度亲缘。

尤其当前 profit_budget **专属机制还0自然差异**。现在再加“幅度+时间”的新profit exit，容易形成退出模板扩张。

建议先让 profit_budget 获得真实专属触发，再决定是否需要 time-under-water 版本。

不是机制不合理，而是**当前不可辨识增量不足**。

---

### 5. partial 后 runner 重新资格
**APPROVE RESEARCH，暂不优先部署。**

这是实质新状态，因为：

`partial fill → 余仓变成新经济epoch`

与“入场后一直沿用旧peak”不同。

但它必须有真实partial fill分母，否则机会太稀。

最干净定义：

- partial SELL真正settled 后才起epoch；
- 新epoch high 从 `realized proceeds + remaining net value` 重新冻结；
- 不继承旧price/economic high；
- 在固定 probation，例如120秒内：
  - 若出现新的余仓经济高点 → runner继续；
  - 否则下一合法帧清余仓。

**必须有 partial baseline**：同样partial后不做requalification、按旧runner继续。

我支持它，但优先级B，因为机会分母依赖真实partial。

---

### 6. 卖笔扩张、价稳分配风险
**APPROVE，优先级A-/B+。**

它比旧activity_failure更清楚：

`买方占优 → 连续转卖方占优 → 经济值无新进展`

不要求已经明显跌价。

关键是不要叫“distribution by whales”或资金净流。

建议：

- 至少3份独立5–60秒frame；
- 首帧 buy share >0.55；
- 后两帧 buy share <0.45；
- 后两帧经济值均没有刷新先前high；
- price仍在先前参考的±3%内，而非已经hard stop。

下一帧退出。

这正好保留22109作为反例：它clock退出时买笔仍强，因此不满足，避免拿两个全损案例调出“一网打尽”规则。

---

### 7. 双边可交易活动确认
**REVISE：Shadow/小额entry challenger可以，不能叫sellability。**

m5出现SELL笔只能说明数据商报告存在卖类交易，**不证明本仓可卖、无honeypot、路由正常**。

如果部署，应该命名：

**two-sided observed activity**

不是 executable / sellability confirmation。

最简单candidate：

- control：原宽entry；
- candidate：当时m5 buys>0 且 sells>0，并在下一独立frame仍双方>0才买。

它可能排掉新币最早阶段，因此需要报告 recall loss。

优先级B。

---

### 8. 下行冲击→修复入场
**先做behavior-hash去重，当前倾向DEFER。**

与旧 `fast_stop_reclaim` / panic reclaim 很可能高度重叠。没有证据证明当前有效实现差异前，不新增。

22212只是“存在恢复案例”，不是机制充分性。

---

### 9. 两侧reserve扩张
**RESEARCH RESERVE，不建议现在部署。**

我R1支持它，但根新材料明确指出目前最关键的问题：

> observer当前没有稳定保留 raw.pairs / reserve字段到策略L0序列。

而且 `FOUNDATION_REVIEW` 当前最应该先修执行时序，不适合顺手扩采集语义。

只有确认：

- actual `liquidity.base` / `quote` 当前自然覆盖；
- surface明确CPMM/V2/PumpSwap；
- 同provider同pair连续保存；
- 不是字符串/单位切换；

再上Shadow。

CLMM继续排除。

---

### 10. 同时机会排序/机制分歧
**DEFER，先Shadow。**

这与现有：

- finite-capital ranker
- observed-set relative resilience
- clone leader

存在明显亲缘。

而且有限slot+不同策略trigger会引入严重选择效应。

最干净的第一步不是Paper，而是冻结同一轮candidate set，记录：

- FIFO/hash baseline；
- 各机制是否赞成；
- 共识数；
- 后续固定horizon。

等有分母再做capital allocation。

---

### 11. 跨池份额迁移/价差
**RESEARCH RESERVE。**

同意根判断：当前observer抛弃raw multi-pair结构；若为它重新改数据保存链，本轮收益/复杂度比不如前3–4项。

以后若实现，必须使用**同一次provider response frozen pool set**，否则两个轮次pool缺失很容易伪造成份额迁移。

---

# 二、我建议本轮真正冻结的少量新实验

不建议11个都做。我会优先只做 **4类**：

### A. `post_signal_chase_guard`
**entry candidate/control**

- 同宽signal；
- 第一合法后帧；
- candidate若追价 >4% 则永久拒绝该episode；
- control正常买；
- 5U、4仓。

**Primary:** candidate vs control成本后PNL、错过右尾、拒绝率。

---

### B. `progress_clock_with_one_extension`
**exit candidate/control**

control = 当前progress_clock。

candidate仅在clock到期时满足“缓慢健康”状态才一次延长180s。

看：

- 两例全损是否仍能逃；
- 三个慢赢家是否保住；
- 晚崩是否增加。

这是目前新自然数据最直接能证伪的tradeoff。

---

### C. `activity_exhaustion_predecline`
**exit candidate/control**

三帧活动窗口上升，但价格增量由正→平、buy share下降；下一帧退出。

control = 不加此exit。

它比已部署activity_failure**提前一个阶段**，辨识性较好。

---

### D. `sell_share_flip_stagnation`
**exit candidate/control**

买占优→卖占优，并且经济值不刷新high；价尚未崩。

与C不要合并：  
C研究 **activity↑但价格响应衰竭**；D研究 **参与方向翻转**。

如果未来自然结果高度重叠，再合并，当前行为条件不同。

---

# 三、工程diff审查：pending BUY

## 3.1 首个合格 receipt

**实现方向基本正确。**

`upsert_chain_meme_trader_pool_mark()` 只有收到比当前pool mark更新的 `observed_at` 才调用 `_settle_pending_market_entry_observation()`。

settler要求：

- exact token；
- chain；
- base token；
- `observed <= ingested <= recorded`;
- age≤15s；
- finite positive price；
- valid liquidity；
- intent created < snapshot observed；
- exact original pool；
- 未expiry。

满足后立即投影，不搜索历史最好价。

所以在当前接收流中确实接近**first eligible receipt semantics**。

---

## 3.2 必须修复项 #1：这会改变旧214未来交易行为

这是我认为最重要的合同问题。

`activate_chain_market_entry_post_observation()` 给**当前 active definition version**写：

`market-entry-post-observation/v1:{version}`

而 `_effective_definition()` 读取这个KV后，整个 active version 的普通主入口从：

`legacy_signal_frame`

变为：

`post_observation_execution`

这虽然：

- 不改policy JSON/hash；
- 不改过去fills；
- 不初始化；

但它**实质改变了旧214未来entry execution行为**。

用户本轮明确：

> 所有已部署旧214含8新臂不可修改/重置。

因此按本轮权限，**不能直接激活这个公共execution epoch到现有214**。

这不是测试能解决的问题，是authority/contract冲突。

### 最小替代

二选一：

1. **不部署此公共变更**，只把后帧执行用于新增策略；
2. 若根认为这是基础工程纠错而非策略修改，必须先取得用户对“旧214未来执行时序可统一修正”的明确授权。

在当前消息授权下，我判：

**BLOCK DEPLOYMENT OF GLOBAL ACTIVATION。**

---

# 四、工程diff审查：receipt证据语义

## 必须修复项 #2：实际fill receipt没有成为position的fill snapshot

当前settler：

- confirmation写入 `kv`，key唯一且 `INSERT OR IGNORE`，因此第一receipt本身不会被覆盖；
- `_project...` 的 `market_price` 用真正后帧价格；
- `filled_at` 用真正receipt recorded_at；
- `signal_price_usd`也正确传入。

但是传给 `_project...` 的：

`snapshot_id = intent["source_snapshot_id"]`

仍然是**signal snapshot id**。

随后position写：

- `baseline_quote_result_id = snapshot_id`
- `entry_snapshot_id = snapshot_id`

于是 position 的 `entry_snapshot_id` 仍指向**决策前signal snapshot**，而真正成交证据只躺在KV receipt。

这会让后续任何“按entry_snapshot_id解释成交时市场状态”的研究再次混淆 signal 与 fill。

### 最小修正原则

不要求新表，但至少需要一个**稳定、可主键引用的真实receipt证据**。

最佳做法是：

- 在settlement接收点把该真实 `TokenSnapshot` append为现有 `token_snapshots` 一行；
- `entry_snapshot_id` 指向这个fill receipt snapshot；
- signal继续由 cohort `source_snapshot_id` 保存；
- receipt KV若要保留可以作为额外audit，但不是唯一fill事实。

如果担心重复插snapshot，可用已有 immutable snapshot路径的最小方式处理；不要复用signal ID。

这是**deployment blocker**，因为本轮核心目的正是修signal/fill时序真实性。

---

# 五、expiry / cash / pending

### Expiry
`due_chain_meme_trader_execution()` 在post-observation模式会把过期 ready/retry BUY 标failed，并重建 `_market_entry_pending_tokens`。这能够释放后续pending reservation。

**但有一个边界：**
settler自身遇到 `recorded_at > expires_at` 只是continue，不主动fail。实际要等下一次 `due_chain...` 才释放。

只要runtime确认该due入口稳定每轮运行，这是可接受的最终一致性；不是必须再加settler写失败。

### Cash reservation
enrollment在新signal时统计已有pending BUY并按arm扣除预留，fill时 `_project...` 又重新读取实际net cash并二次检查。

这是正确的双层保护。

注意fill时如果某arm现金已不够，该arm会：

`skipped_cash_unavailable_at_fill`

但共享cohort其余arm可成交。对于旧主family这是现有账户独立语义，可接受。

### max 8
继续复用 max_pending_buy_intents，没有新增无限队列，正确。

---

# 六、gross/net修复

**APPROVE。**

当前代码已经正确分开：

普通mark：

- `gross = sell_terms(...).gross_usd`
- `net = ...net_usd`

amountful：

- `gross = minimum_output_raw / 1e6`
- `net = net_recovery_usd`

fill的 `gross_usd` 用gross；后续：

- `realized_proceeds`
- `cumulative_pnl`
- `formal_net_recovery`

用net。

当前fee=0所以生产历史金额不变；以后fee非零时字段语义才真正区别。

没有看到二次扣fee。

历史不回写，也正确。

---

# 七、外部证据与根提案的关系

R1_EXTERNAL_EVIDENCE对当前最有用的是：

**高activity既可能是持续需求，也可能正是pump结束前的爆量。**

这和本地新事实高度一致：

5个最终亏损baseline在+120s时全部：

- price高于entry；
- reported liq高于entry；
- buy share≥0.5；

仍最终亏损。

因此根提案中我明确反对再使用：

`price↑ + liq↑ + buy share高 → 延长持仓`

作为足够条件。

这也是为什么我的“slow extension”规则必须只在**clock本来要退出时给一次短延期**，而不是把这些字段解释成持续赢家确认。

---

# 八、最终R2结论

### 建议现在优先冻结
1. post-signal chase guard
2. progress-clock one-extension
3. pre-decline activity exhaustion
4. sell-share flip stagnation

### 暂缓/储备
- profit retrace duration
- partial-runner requalification（等partial分母）
- two-sided activity
- down-shock reclaim（先去重）
- reserve expansion
- opportunity consensus ranking
- cross-pool migration/dispersion

### 工程
**gross/net：GO。**

**pending BUY：逻辑方向GO，但当前不能部署，两个必须解决的问题：**

1. global activation 会改变旧214未来执行语义，与本轮“旧214不可修改”冲突；
2. 真正后帧receipt没有成为 `entry_snapshot_id`，signal/fill证据仍被主键混淆。

---

## 实际读取

- `ROUND2/R2_PROPOSALS.md`
- `ROUND2/PATH_AND_REGIME.md`
- `ROUND2/FOUNDATION_REVIEW.md`
- `ROUND2/R1_EXTERNAL_EVIDENCE.md`
- `src/memetrader/store.py`
  - `_settle_pending_market_entry_observation`
  - `enroll_chain_meme_trader_v6`
  - order-intent pending/expiry
  - `chain_meme_trader_market_mark_targets`
  - pool-mark settlement hook
  - `_project_chain_meme_trader_market_entry`
  - market SELL gross/net settlement
  - execution activation/effective-definition相关段

未运行全历史SQL，未写代码、DB或Runtime。

**CROSS_REVIEW RESULT：根提案应继续收敛；优先研究“追价成本、慢赢家许可、活动响应耗尽、卖方份额翻转”，不要现在把reserve/multipool和更多profit-exit一起铺开。工程上先解决旧214权限冲突和fill receipt主键语义，再谈公共pending BUY部署。**
