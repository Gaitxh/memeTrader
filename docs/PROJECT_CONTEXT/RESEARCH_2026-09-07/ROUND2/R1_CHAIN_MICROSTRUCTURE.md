[GXH_C2C_V3]  
MESSAGE_ID: C2C-20260907-024100-OPEN-R1-CHAIN_MICROSTRUCTURE-RESULT  
REPLY_TO: C2C-20260907-024100-OPEN-R1-CHAIN_MICROSTRUCTURE  
TYPE: RESULT  
CYCLE_ID: open-mechanisms-round2-20260907  
ROLE: CHAIN_MICROSTRUCTURE  
SENSITIVE_DATA: NONE  
MODEL_STATUS: **Chat实际模型/推理档位不可由项目侧核验，记为未知；不依据自述认定切换模型。**

## 结论

**PROCEED_NEW_MECHANISM_RESEARCH / NO_ALPHA_CLAIM**

本轮实际只读 `E:\memeTrader`，没有重跑全历史扫描、没有写代码/DB/Runtime、没有访问secret。`ROUND2` 当前我读取时只有 `RESEARCH_REQUEST.md`，所述 `PATH_AND_REGIME.md / FOUNDATION_REVIEW.md / EXTERNAL_NEW_EVIDENCE.md` 尚未落地，因此以下不假装使用未出现报告。

一个新的高价值发现是：**当前低成本输入里其实已经包含比 `liquidity_usd` 更细的微观结构信息，却尚未充分用作机制。**

DexScreener 官方 pair 返回不仅有：

- `priceUsd`
- `txns`
- `volume`
- `liquidity.usd`

还包含 **`liquidity.base` 与 `liquidity.quote`**，并且 token-pairs 接口一次返回一个 Token 的多池集合。citeturn709064search0

当前 `collectors.py` 的 `batch_quote()` 已实际把**一个 Token 同次返回的所有 pools 放进 `snapshot.raw["pairs"]`**，同时正常快照仍保存 selected pair。这意味着几个真正新的机制可以做到：

> **不增加外网API，只在已有响应上做有限计算。**

---

# 一、优先级最高的新机制：双储备方向，而非 USD liquidity

## M1. `two_sided_reserve_expansion`

### 假设
对于 **CPMM/V2/PumpSwap 常数乘积类池**，如果同一个原池连续帧中：

- raw base reserve ↑
- raw quote reserve ↑
- 价格没有同步暴涨
- 原池身份/source连续

那么它比单纯 `liquidity_usd ↑` 更接近“池两边实际余额共同增加”的状态。

这与上一轮 `price_then_depth` **行为不同**：后者只研究数据商报告的 USD liquidity 追认；本机制看两侧原始数量的共同变化。

### 为什么值得研究
Raydium CPMM 的 add/remove liquidity 本身就是两边资产按池比例进入/离开；withdraw 销毁LP并按比例取出两种资产。citeturn272069search2turn272069search4  
Pancake V2 同样要求成对增加流动性，removeLiquidity 返回两种资产。citeturn477110search0turn477110search2

### 反证
这**不能叫 confirmed LP deposit**：

- swap fee 会改变储备；
- transfer-tax/rebase/token扩展可能影响余额；
- 聚合器字段可能缓存/异步；
- CLMM不能套这个解释。

因此建议名字使用 **two-sided reserve expansion proxy**。

### 下一自然验证
5U candidate vs 同entry control：

`两边reserve共同扩张 → 后续15m成本后路径/死亡率`

若只是在行情上涨时机械共变，淘汰。

**优先级：A。**

---

# 二、M2. `reserve_flow_state_classifier`：区分 sell drain / buy drive / withdrawal-like

这是我认为比继续堆买卖笔数阈值更有信息量的方向。

对于恒定乘积类原池，两份可靠连续帧可以形成粗分类：

- **base reserve ↑ + quote reserve ↓**  
  → 与 Token 被卖进池、quote资产被取走的方向一致；
- **base reserve ↓ + quote reserve ↑**  
  → 与 Token 被买走、quote资产进入池的方向一致；
- **base ↓ + quote ↓**  
  → 更接近两侧流动性共同退出的异常形态；
- **base ↑ + quote ↑**  
  → 更接近双侧增加/费用累计等状态。

这不是逐笔真实净流，也不是钱包证据。

### 新策略形式
不建议主要做entry，优先做**持仓退出/风险状态**：

> 价格还没跌穿hard stop，但 quote reserve连续下降、base reserve持续增加，则提前识别“sell-drain-like”状态。

这与现有：

- `price↓ + liq↓`
- `price↓ + liq↑`
- buy/sell count
- actual-flow限定Solana池

均不同。

### 外部机制依据
CPMM swap 是精确输入/输出沿池储备成交，而 withdraw 是LP销毁并取出两资产；协议动作的方向结构确实不同。citeturn272069search4turn272069search6

**优先级：A。**

---

# 三、M3. `original_pool_dominance_decay`

当前 DexScreener batch 响应本身保留多池，因此可以研究：

`原池liquidity / 同次可见所有该Token池liquidity`

而不是只看原池绝对流动性。

### 假设
一个 Token 总流动性看起来没坏，但：

- 原池占比从 dominant 快速下降；
- 新池/兄弟池份额快速增加；
- 原池价格/活动开始落后，

这是**market-surface fragmentation / pool handoff**，经济含义不同于普通价格回撤。

### 使用方式
优先作为：

- 已持仓风险；
- generic pool handoff研究；
- 新 dominant pool 的独立 reawakening cohort 候选。

不能直接用新池价格替原仓SELL——现有 original-pool Paper 语义应保持。

### 反证
DexScreener token-pairs是**供应商可见池集合，不是全链完整pool universe**。官方接口只承诺返回其token-pairs数据。citeturn709064search0

所以：

- 某池没出现在下一响应 ≠ liquidity=0；
- 只能比较完整同次response中的相对share；
- coverage变化必须UNKNOWN。

**优先级：A-/B+。**

---

# 四、M4. `pool_handoff_confirmation`

M3是风险状态；M4是重新入场状态，两者不要合并成一个策略。

### 状态机

1. 旧池原本dominant；
2. 旧池份额下降；
3. 另一个**同Token**池连续成为dominant；
4. 两池 USD price 收敛而不是长期异常分叉；
5. 新池自身liquidity/activity持续；
6. 再等下一独立新池frame入场。

它与现有 precise migration 不同：

> **不要求存在官方 migration event。**

因此能覆盖普通跨池生命周期、社区迁池、DEX切换等。

Raydium官方甚至明确描述 AMM v4→CPMM migration 是“先撤旧池，再向新池加流动性”的两步过程，所以跨池流动性转移确实可以产生这种 observable handoff。citeturn272069search1

### 反证
没有官方迁移证据时，只能叫 **observed pool handoff**，绝不能叫 canonical migration。

**优先级：B+。**

---

# 五、M5. `cross_pool_price_dispersion_risk`

同一 Token 同时有多个pool时，利用同次返回：

`max(priceUsd)/min(priceUsd)-1`

但只在具有有效liquidity的可比池上。

### 经济假设
极大的跨池价差可能表示：

- 某薄池被局部推价；
- stale/孤立market surface；
- liquidity碎片化；
- 路由/套利尚未恢复一致性。

因此可以做：

> 同样L0 momentum下，跨池价格高度分叉的candidate vs price-converged control。

这直接攻击一种历史右尾假象：

**一个极薄池涨很多，不等于Token整体有可兑现市场。**

### 反证
跨池价差也可能是真实、短暂而有利的price discovery；因此不应设 universal hard reject。

**建议只做5U独立风险分层或entry challenger。**

**优先级：B。**

---

# 六、M6. `next_frame_edge_consumption`

这是交易经济性方向，我认为非常实用，而且几乎零新增成本。

当前严格合同已经：

`signal frame → next independent frame → Paper BUY`

但不同信号在等待下一帧过程中可能：

- 已经涨太多；
- 已经跌掉；
- liquidity发生巨大变化。

现在 BUY仍以**下一帧市场价再+4%**执行。

### 新假设
记录：

`next_frame_price / trigger_price`

如果一个信号经常在真正允许买入之前已经被市场吃掉大部分edge，那么它即使“方向判断正确”，也可能不赚钱。

可做独立 entry treatment：

**signal仍成立，但如果confirmation frame出现过度追价则拒绝。**

注意不是优化某个固定“+X%”阈值；第一版应给一个明确宽松、非历史最优的成本预算，并用control验证。

### 为什么它与已有策略不同
它不预测Token涨跌，而测试：

> **信号捕获速度能否在4%+4%成本下保留足够经济余量。**

尤其当前请求明确“成本后盈利且工程真实”，这一方向很贴目标。

**优先级：A。**

---

# 七、M7. `observability_survival_control`

当前基线事实很刺眼：

- RH 持仓报价 age P95 已到约718秒；
- SOL P95约345秒；
- 大量 coverage gap / failure。

这些不是alpha，但直接决定**策略退出能不能及时观察**。

### 新机制
同一个普通entry拆：

**candidate：**
买入前要求原池近期已经形成连续可观察序列，例如：

- ≥N个真实更新；
- 无超长gap；
- 没有provider missing被伪刷新；
- 原池身份持续存在。

**control：**
原策略，只要当前frame合格即可。

### 研究问题
> “容易持续观测的池”是否牺牲一些早期右尾，但显著降低核销、陈旧退出和无法管理仓位的成本？

这是 execution-quality / trackability treatment，不称市场alpha。

这比再要求精确router quote更符合用户现行轻量Paper合同。

**优先级：A-/B+。**

---

# 八、钱包证据：本轮不建议再造“聪明钱包”新entry

项目当前已经有：

- effective breadth；
- common funding；
- first-observed buyer；
- creator/early-holder；
- wallet观察等机制。

而上一轮外部纠错已经说明钱包论文最新版的金额结果并不稳健，不能把旧的大幅效应当wallet alpha。

因此本轮钱包方向我只建议一个**风险型研究储备**：

### `funding_concentration_acceleration`
不是“某钱包聪明”，而是：

> 当前已观测买方中，共同资金关系/资金来源集中度是否在价格上涨过程中持续上升？

如果：

`price↑ + apparent breadth↑ + funding concentration↑`

那么“地址扩散”可能只是关联钱包拆分。

但当前 common-funding 覆盖有限，所以我给：

**RESEARCH RESERVE，暂不建议立即部署。**

缺证据绝不能解释成“资金独立”。

---

# 九、CLMM：明确不制造假机制

Raydium CLMM官方说明，LP选择价格区间，position可变成 **out of range**，而增加/减少流动性会改变position/tick上的有效liquidity。citeturn709064search2turn709064search4

因此：

> 对CLMM，仅凭DexScreener `liquidity.usd` 无法知道当前价格附近真正有效深度。

所以我**反对**把 M1/M2 双reserve机制直接跨到 CLMM。

除非当前系统以后已有免费的 tick/range state 输入，否则：

- CPMM/V2/PumpSwap → 可研究reserve-state；
- CLMM/V3 → 只做surface分层/UNKNOWN。

这正是“工程真实”比“策略数量”重要的地方。

---

# 十、推荐这一轮优先自然验证的顺序

### 第一梯队：当前已有输入、成本最低、与214行为差异明显
1. **next-frame edge consumption**
2. **two-sided reserve expansion**
3. **reserve-flow state / sell-drain-like exit**
4. **original-pool dominance decay**
5. **observability-survival control**

### 第二梯队
6. **pool handoff confirmation**
7. **cross-pool price dispersion**

### 暂只研究
8. funding concentration acceleration
9. CLMM range-liquidity类机制

我不建议同时注册十几个阈值版本。每个机制最多一个candidate + 必要control。

---

# 十一、L0代理 vs 真实链上证据必须这样命名

| 输入 | 可以说 | 不能说 |
|---|---|---|
| buy/sell count | 买卖笔结构 | 真实买卖资金流 |
| `liquidity.usd` | 数据商报告池流动性 | LP净注资 |
| raw base/quote reserve连续变化 | reserve-direction proxy | 已确认LP add/remove |
| 多池同次响应 | observed pool fragmentation | 全链pool份额 |
| common funding evidence | 已观察资金关系 | 同一控制人 |
| wallet address | 地址 | 独立自然人 |
| Dex pool不存在/缺失 | provider未观察 | 池已撤 |
| actual decoded transfer notional | 当前覆盖内真实金额流 | 全池完整order flow |

---

# 十二、外部一手/官方证据与反证

- DexScreener官方API确认 token-pairs 返回一个Token的多个pair，并公开 `liquidity.base/quote/usd`、txns、volume、price等字段；300 req/min是接口上限，但本提案优先复用系统已经取得的响应，不增加调用。citeturn709064search0
- PumpSwap公开SDK明确同时具有 deposit、swap、withdraw，所以普通PumpSwap liquidity不能天然解释成不可撤。citeturn315919search0
- Raydium CPMM明确允许LP销毁LP token并按比例取回两种资产。citeturn272069search4
- Pancake V2同样允许add/remove pair liquidity。citeturn477110search0turn477110search2
- Raydium CLMM明确是range-based concentrated liquidity，并允许DecreaseLiquidity；因此普通总liquidity指标不能安全地当成当前价位有效深度。citeturn709064search2turn709064search4

这些资料支持的是**市场机制可发生**，不是上述候选已经有正期望。

---

## 实际读取

- `AGENTS.md`
- `.agents/skills/memetrader-forward/SKILL.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/ROUND2/RESEARCH_REQUEST.md`
- `docs/PROJECT_CONTEXT/CURRENT_OBJECTIVE_AND_PLAN.md` 当前首段
- `src/memetrader/capital_policies.py`
- `src/memetrader/capital_context.py`
- `src/memetrader/collectors.py` DexScreener pair/batch/raw-pairs相关段
- 对 `src/memetrader` 做了有界关键词定位，确认既有 migration、wallet、surface、L0、entry/fill 等方向，避免明显重复。

## 最终首轮判断

**最值得根代理继续验证的新空间不是更多“volume/buy-ratio/momentum”组合，而是：**

> **raw reserve方向 → 原池在多池中的相对地位 → 跨池价格一致性 → 信号到真实下一帧时edge被消耗多少 → 这个池是否具备持续可观察性。**

这些方向多数可以复用**已经在系统内取得的数据**，不需要新API，也更直接攻击当前 Paper 最容易产生虚假漂亮收益的地方：**薄池、错表面、fragmentation、迟到成交和无法及时退出。**
