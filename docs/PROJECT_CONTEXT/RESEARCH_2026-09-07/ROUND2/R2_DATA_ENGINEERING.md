[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-030700-OPEN-R2-DATA_ENGINEERING-RESULT  
REPLY_TO: C2C-20260907-030700-OPEN-R2-DATA_ENGINEERING  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: DATA_ENGINEERING  
SENSITIVE_DATA: NONE  

**DISPOSITION: REVISE_FOUNDATION_DIFF_BEFORE_DEPLOY / NARROW_R2_MECHANISMS / NO_ALPHA_CLAIM**

模型：GPT-5.6 Sol；实际宿主推理档位**不可核验，记未知**。

本轮实际只读 `R2_PROPOSALS.md`、`PATH_AND_REGIME.md`、`FOUNDATION_REVIEW.md`、`R1_CHAIN_MICROSTRUCTURE.md`，以及未部署 `store.py` 中 post-observation BUY 与 gross/net 改动。没有运行全历史SQL、没有写代码/DB/Runtime。

## 一、未部署底座diff：一个必须修复项

### 1. post-observation BUY的大方向正确

当前diff已经具备：

- signal/cohort保持immutable；
- 新execution epoch单独存在，不改旧历史fill；
- pending BUY复用order intent；
- 最大8 pending；
- admission时按arm独立现金预留；
- 90秒expiry；
- pending token纳入held watch，且带冻结原池；
- 重启后可从ready/retry intent恢复pending token集合；
- receipt要求  
  `decision < observed <= ingested <= recorded`；
- 15秒新鲜；
- 正价格、完整有效liq、原池一致；
- 第一个符合条件的本地receipt就消费，不择后面更好价格；
- receipt用唯一KV key `INSERT OR IGNORE`冻结；
- 旧signal price与实际后帧fill price已分离保存；
- execution activation独立于policy hash，所以旧214策略定义/资金期/历史本身没有重写。

这些都符合FOUNDATION_REVIEW提出的最小方向。

### 2. **必须修：0实际投影也把intent写成filled**

当前 `_settle_pending_market_entry_observation()`：

1. 先冻结首个receipt；
2. 调 `_project_chain_meme_trader_market_entry(...)`；
3. **忽略其返回的projected数量**；
4. 无条件：

`UPDATE ... order_intents SET status='filled'`

而 `_project...` 自己会在fill时重新检查实际现金。于是存在具体反例：

> signal时账户因pending reservation有钱 → intent成立 → 等待期间其他独立路径消耗该arm现金 → 首receipt到达 → 二次现金检查拒绝0个position → intent仍被标记`filled`。

影响不是资金超支，而是**执行事实造假**：

- execution denominator把“收到receipt但没有任何BUY”记成filled；
- 后续研究无法区分fill与cash-unavailable-at-fill；
- receipt已经immutable，因此也不会等下一报价，这本身没问题，但终态必须如实。

### 最小修正

根据 `_project...` 返回值：

- `projected > 0` → `filled`
- `projected == 0` → 明确 `failed` / `skipped_cash_unavailable_at_fill` 类终态

receipt仍保留，**不要改成等待下一帧重新尝试**，否则会破坏“首个合格receipt”合同。

如果冻结参与组允许部分arm因现金变化被跳过，则intent可为filled，但必须由已有participant outcomes明确展示谁实际projected、谁skipped；不能把cohort级filled解释成所有参与账户都fill。

这是我本轮唯一明确的**部署前工程阻断**。

---

## 二、gross/net修复：当前实现方向正确

我R1指出的字段语义问题已经在未部署diff里正确拆开：

普通SELL：

- `gross = sell_execution["gross_usd"]`
- `net = sell_execution["net_usd"]`
- fill/trade `gross_usd` 写gross；
- realized proceeds / cash / PNL使用net。

amountful：

- gross使用 `minimum_output_raw / 1e6`
- net使用已有 `net_recovery_usd`
- 没有重新重复扣extra fee。

这符合字段语义。

当前fee=0，部署前后现存PNL不会因此变化；历史旧行也不应回写。

`fee > proceeds` 仍按冻结的 `max(0,gross-fee)`合同，本轮不建议借机扩大定义。

---

# 三、R2根提案：哪些重复、哪些有信息增量

## 1. 成交追价预算：**APPROVE，优先级最高**

这与链上微观结构R1的 `next_frame_edge_consumption` 是同一机制，**不要再注册两个名字**。

它直接利用这轮最重要的新工程事实：

> signal与真正可买的后帧之间存在真实价格变化。

而且新公共post-observation执行修复后，这个量才具有一致经济意义。

### 推荐冻结形式

同一宽入口：

- control：第一个严格后receipt照常买；
- candidate：仅当  
  `fill_receipt_price / frozen_signal_price - 1 <= chase_budget`
  才买；
- candidate拒绝后该signal永久consumed，**价格后来回落也不补买**；
- candidate veto不能取消control；
- 同cash/slot admission后再做treatment。

第一版budget可直接用**当前往返成本带8.333%作为非拟合边界**，而不是从20个赢家找最佳5%、7%、12%。

这是少数我认为既有经济含义、又非常容易干净辨识的新实验。

---

## 2. 缓慢稳定持有许可：**REVISE，必须与progress_clock配对，不单独自由运行**

新事实非常清楚：

16个成熟clock pair：

- 2改善；
- 3恶化；
- 11相同；
- 总差+7.508U；
- median差0。

因此不能说“180秒早退有效”，也不能反过来说“慢持更好”。

更有信息量的实验不是另造一个maxhold变体，而是：

**同一progress-clock触发点上的二分 treatment：**

- A：现有clock退出；
- B：仅当过去一个固定窗内 `economic_value`累计有正进展、liq仍>=基线一定比例、activity未恶化时，允许**一次**短延期；
- 延期用尽后不能再次renew；
- hard stop/writeoff不受延期影响。

我建议只允许**一次+120秒**这类预注册固定延长，不进行120/180/300参数网格。

评价：

- 救回多少慢赢家；
- 额外承受多少晚崩；
- capital-time占用。

这比注册“慢持策略”更可辨识。

---

## 3. 活动边际响应耗尽：**REVISE，但可做**

它与现有 `activity_failure` 不完全重复：

- 已有：activity↑且**价格已经跌**
- 新提案：activity继续↑，但价格响应从正变近0，并且买卖结构恶化，**尚未明显跌**

所以确实是更早阶段。

但最大问题是滚动m5窗口：

`volume_t - volume_t-1`

不是两帧间新成交额。

### 最小规则

不要使用“成交增量”。

冻结三个≥15秒帧，只比较供应商滚动状态：

- m5 activity level连续不低；
- 第1→2价格增幅明显为正；
- 第2→3价格增幅≤小的固定near-zero带；
- buy share同步下降并进入≤50%附近。

名字建议：

**reported-activity / price-response exhaustion**

不能叫资金流耗尽。

可与相同entry baseline做exit challenger。

---

## 4. 利润回吐持续时间：**MERGE到profit_budget family，不要再算新entry机制**

当前profit_budget还没自然产生专属exit，因此没有证据否定它。

“跌破利润边界后持续N秒才退”是**同一个profit-preservation机制的时间确认版**。

不要同时注册：

- instant profit budget
- 15s budget
- 30s budget
- 60s budget

更干净的方案是**一对**：

- baseline：当前幅度型profit_budget；
- challenger：同一个profit boundary，但必须连续可观察30秒仍在boundary下才退出；恢复则取消。

source/gap/NULL必须暂停/清计时，不能把断采算持续。

这回答一个单一问题：

> 立即锁盈 vs 给正常波动一个固定恢复窗口。

---

## 5. partial兑现后的runner重新资格：**APPROVE，但只做真实partial-fill后的exit实验**

这是本轮比较有信息量、而且与旧profit-lock bug不同的机制。

必须从**实际partial fill completed_at**开始新epoch：

- 旧running high全部废弃；
- 冻结剩余quantity、已实现proceeds、余仓经济值；
- 后续只有新余仓经济高点能更新runner状态。

建议 paired：

- control：partial后沿现有规则；
- candidate：partial后120秒 probation；
  - 期间若形成新的净经济高点且原池仍完整 → 继续runner；
  - 否则余仓退出。

没有partial fill就没有该实验机会。

这是比修旧`principal_recovered` flag来包装新机制干净得多。

---

## 6. 卖笔扩张、价格稳定分配风险：**与#3二选一，不要两者同时首批注册**

#3研究：

> 活动仍强，但价格响应耗尽。

#6研究：

> 买占优→卖占优，价格尚未显著下跌。

两者在现有滚动count输入下高度相关。

如果首批同时上线，几十个样本很难解释到底是：

- activity-response失效；
- 还是sell-share转换。

我的建议首批只保留**#6**，因为行为语义更清楚：

- 连续3帧；
- buy share从>55%转到<45%；
- economic value未创新高；
- price尚未触发hard stop；
- 下一独立帧退出。

#3先作为feature telemetry记录，不另开账户。以后若发现大量“share未翻转但activity-response耗尽”的机会，再独立注册。

---

## 7. 双边可交易活动确认：**暂不支持Paper entry，先Shadow**

`m5 sells > 0` 并不证明：

- 当前持仓能卖；
- 卖单来自独立地址；
- 路由存在；
- 卖出的不是微尘交易。

LAMBO/SHAR类外部反例可以说明“看见买盘不等于可兑现”，但不能把“看到1笔SELL”升级成可卖证明。

如果实施成hard entry treatment，很可能只是过滤低活动币，并与普通activity门重复。

建议先记录：

`two-sided-count-presence`

作为描述性Shadow，等它对writeoff/no-route/尾损有增量信息再升Paper。

**当前否决新Paper ID。**

---

## 8. 下行冲击→冻结参考→修复入场：**先与fast_stop_reclaim精确去重**

PATH_AND_REGIME只提供一个恢复案例22212，同时也有不恢复反例。

机制本身有价值，但仓库已经有：

- fast_stop_reclaim
- panic reclaim
- pullback reclaim
- boundary retest

如果有效旧策略已经做到：

`下行冲击 → 冻结低点/参考位 → 后帧收复 → 下一帧entry`

就不应新建。

只有旧 `fast_stop_reclaim` 是“已有持仓止损后再入”而新机制是“未持仓市场冲击后的首次修复entry”等**实际状态机差异**时才值得新ID。

当前我给：**DEFER UNTIL BEHAVIOR-HASH DIFF**。

---

## 9. 两侧reserve同步扩张：**高价值，但当前只Shadow**

我同意链上微观结构R1：这比单一USD liquidity更有研究信息。

但R2提案自己也承认：

- pool type必须明确；
- CLMM不能套；
- 当前实际覆盖尚未核验。

而 `liquidity.base/quote` 是聚合器字段，不是链上vault differential。

因此第一步应该是零交易权限的coverage probe：

- CPMM/V2/PumpSwap明确surface；
- 同source同pool；
- base/quote两侧字段完整率；
- 时间连续性；
- source cache generation。

达到可用覆盖再升级5U Paper。

**不建议现在直接注册交易臂。**

---

## 10. 同时机会排序：**Shadow优先，暂不改交易**

我反对在当前阶段把214策略之外再引入复杂全局排序，因为：

- 同时机会集合的冻结定义尚未完成；
- discovery frequency跨链不同；
- pending/slot/cash会改变谁“同时”存在；
- 排序本身会改变机会暴露，随后难与原策略比较。

最小高信息方案：

在同一个已有evaluation round中冻结候选ID集合，离线/Shadow记录：

- FIFO/hash control；
- 某单机制score leader；
- 多机制多数票leader。

不影响买入。

如果后续leader在固定horizon和真实Paper opportunity中有稳定增量，再建新账户。

---

## 11. 跨池份额/价差：**当前DEFER**

CHAIN_MICROSTRUCTURE指出原始Dex response有`raw.pairs`潜力，但R2提案也明确当前observer丢弃它。

在：

- 完整同次pool-set无法低成本冻结；
- provider coverage变化无法区分；
- pool missing不能解释为0；

之前，任何“原池占比下降”都有严重不可辨识性。

不能只为这个机制重新扩大数据模型。

先确认可以在**不增加API、不阻塞held、bounded存储**下保留同次pool-set，再研究。

当前不注册Paper。

---

# 四、这一轮我建议真正冻结的少量实验

如果根代理要收敛到高信息量，而不是把11项都实现，我支持优先：

1. **Post-signal chase budget candidate vs unconditional next-receipt control**  
   最干净，直接利用即将修好的execution kernel。

2. **Progress-clock vs one-shot slow-progress permission**  
   直接回答当前自然pair的真实矛盾。

3. **Buy→sell count-share distribution-risk exit vs baseline**  
   与现有activity_failure有清楚时序区别。

4. **Post-partial runner requalification vs post-partial baseline**  
   只在真实partial fill后参与。

5. **Profit-budget amplitude vs fixed-duration-confirmed profit-budget**  
   如果资源允许；否则等现有profit_budget先自然触发再注册。

其余：

- reserve两侧 → Shadow coverage；
- opportunity ranking → Shadow；
- two-sided count confirmation → Shadow；
- cross-pool → defer；
- recovery entry → 先去重。

这比一次新增11个账户更容易得到可解释结果。

---

# 五、未部署执行修复的另两个说明

### `entry_snapshot_id`现在仍指signal snapshot，不是后receipt

当前post-observation settler把：

- `market_price`设为真实receipt price；
- `signal_price_usd`单独设为signal price；

但 `_project...` 仍收到：

`snapshot_id = signal source_snapshot_id`

因此position的 `entry_snapshot_id` 仍是signal snapshot。

这不一定阻止部署，因为首receipt已单独immutable保存在：

`market-entry-post-observation/receipt:<version>:<cohort>`

但今后任何分析**不能再把entry_snapshot_id解释成实际成交snapshot**。

最小要求：

- 文档/API/研究明确signal snapshot与execution receipt是两种证据；
- 如果以后需要统一join，使用receipt evidence，不要偷偷改历史字段。

我不建议为此新建表或阻塞当前小修。

### activation是execution epoch，不是“旧214完全没有行为变化”

启用 `post_observation_execution` 会改变当前主入口未来的BUY时序，因此经济行为确实发生变化。

它没有改：

- policy定义/hash；
- 资金期；
- 已完成交易；
- 上一轮8个isolated机制。

但报告必须说：

> 旧214保持策略合同；普通主入口从某execution activation起采用更严格后receipt成交。

不能写“旧214行为完全未改变”。

这是执行真实性修复，不应倒写旧结果。

---

# 六、最终结论

**部署前必须修：**

只有一项：

> 首receipt实际 `projected==0` 时不得把BUY intent标成`filled`。

同时用现有participant outcomes保持partial projection事实可追。

**gross/net修复：通过我的只读审查。**

**R2新机制：不要全做。**

优先冻结4–5个能够回答单一经济问题的candidate/control；reserve、跨池、全局排序等先Shadow或defer。

最重要的原则仍然是：

> **真正下一可得报价 + 真实成本 + 同机会对照 + 不把rolling代理/coverage状态包装成链上事实。**

当前任何自然结果，包括progress-clock约+7.5U paired delta和共同+42.7U赢家，都不足以称alpha；代码测试通过同样不构成经济证据。
