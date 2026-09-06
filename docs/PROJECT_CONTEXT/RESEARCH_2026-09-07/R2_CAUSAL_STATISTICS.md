# R2 CAUSAL_STATISTICS

Source Chat: 6a9d94b1-0a10-83ee-ad29-cb5abbb949c8
Actual response; model setting not independently verified. Markdown trailing whitespace normalized.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R2-CAUSAL_STATISTICS-RESULT
REPLY_TO: C2C-20260907-R2-CAUSAL_STATISTICS
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: CAUSAL_STATISTICS
BLOCKS_RELEASE: true
DISPOSITION: **PROCEED_BOUNDED_PAPER / BLOCK_ALPHA_PROMOTION**
MODEL: GPT-5.6 Sol；项目侧无法独立核验具体 reasoning 档位，标记 **未核验**
SENSITIVE_DATA: NONE

## 1. R2 总裁决

我支持继续做 **严格前向、小额、可证伪 Paper**，但不同意把当前根草案的“8 个已有 + 8 个新增”原样全部注册成 16 个新核心策略。

原因不是“没有 alpha 所以什么都不能做”。恰恰相反：

> **目前最合理的动作就是部署少量机制真正不同的前向实验，以获得未来证据。**

但必须把两件事严格分开：

**阻止盈利宣称：YES，全部候选当前都被阻止。**
最终 V002 截止统计只有 **1.28936 小时**；6,681 个闭环只是账户生命周期，只有 341 个闭环 token，而且大量策略共享同一机会。当前不存在足以宣称长期正期望、alpha、Champion 或扩大资金的证据。

**阻止研究型小额 Paper：NO，并非全部阻止。**
只要某候选：

- 使用当时真实可得输入；
- 与旧机制有实际行为差异；
- 有冻结 baseline/control；
- 新 frontier、无回填；
- 5U 等小额；
- 不新增高成本请求；
- 不把 missing 当 0；
- 不重置旧策略/账户；
- 明确失败条件；

就应该允许继续自然前向验证。

---

# 2. 我实际读取的共同证据

本轮通过 `@笔记本量化MCP-官方隧道` 实际只读：

- `E:\memeTrader\AGENTS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R2_DESIGN_QUESTIONS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/HISTORICAL_EVIDENCE_MAP.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/HISTORICAL_STATISTICS.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/EXTERNAL_EMPIRICAL_EVIDENCE.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_STRATEGY.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_MICROSTRUCTURE.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_ADVERSARIAL_RISK.md`
- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R1_EXTERNAL_RESEARCH.md`

没有运行大 SQL、没有修改 Runtime/代码/DB、没有访问秘密配置。

本地 `TOKEN_PRECURSOR_EVIDENCE.md` 仍在研究中，**本 R2 不使用其未完成结果**。

---

# 3. 完成后的全历史统计改变了什么

## 3.1 不能再用“交易很多”解释成熟

最终资金期：

- 运行仅 **1.28936 h**
- 8,413 BUY
- 6,681 完整闭环
- 341 个闭环 token
- 胜率 17.00%
- PF 0.231
- 期望 -6.01U
- 中位数 -4.16U
- P05 -20U
- P95 +13.66U
- 1,932 次模拟 writeoff

206 个策略产生很多复制账户，因此：

> `6,681 closed` 不能被解释成 6,681 个独立市场实验。

这也是当前所有“alpha 已经出现”的硬阻塞原因。

---

## 3.2 当前唯一正总 PNL arm 也不能晋级

`watched_wallet_confirmed_entry_control_v1`：

- 43 BUY
- 39 closed / 39 token
- +4.83U
- 中位数 -0.264U
- remove-best-3 后 **-29.61U**

因此现在连“唯一正 arm”都明显 winner-sensitive。

不能由此声称 wallet alpha。

---

## 3.3 当前最有价值的 paired 结果其实是反证

共同闭环 intersection：

- `l0_continuation_failure`：91 个，candidate 相对 control **+21.79U**
- 但 candidate/control 全部仍分别约 **-642.68 / -648.07U**

所以它目前只是：

> **少亏线索**

而不是盈利策略。

更重要的是：

- `l0_profit_lock`：59 个 intersection，**-62.54U**
- `experiment_conditional_runner`：108 个 intersection，**-84.84U**

这两条对“拿更久”和“看起来合理的 profit-lock”都形成了实际反证。

---

# 4. 对其他 R1 的明确反驳/限定

## 4.1 不同意 R1 STRATEGY 把 profit-lock 放在优先核心候选

R1 Strategy 把：

- continuation failure；
- profit lock；
- peak/drawdown；

一起列入最值得保留的退出主线。

我只部分同意。

**Continuation failure：支持继续。**

**Profit-lock：降级。**

因为完成后的全历史统计已经新增了当时 R1 看不到的证据：

`l0_profit_lock candidate-control = -62.54U / 59 paired closures`

因此：

> 当前这个具体实现不能因为“利润保护”这个机制在直觉上合理就进入核心候选。

保留原 ID 和历史，继续作为 comparator 可以；**不要重新复制成一个所谓最终策略。**

更合理的是保留更广义的：

**cost-cleared profit preservation / peak-drawdown exit family**

但必须用不同于当前失败实现的新、冻结规则再前向验证。

---

## 4.2 限定 R1 STRATEGY 的“参与扩散突破”

这个方向机制上成立，但地址 ≠ 人。

完成后的证据地图也确认：

- first-observed buyer；
- wallet observer；
- common funding；
- issuance holder；

存在明显覆盖限制。

所以：

**可以是条件型小额实验，不应进入所有 Token 都必须满足的核心 hard gate。**

否则会把 input coverage 当经济信号。

---

## 4.3 不完全接受 R1 MICROSTRUCTURE 的“寻找 +15%～30% impulse”表述

R1 Microstructure 正确指出：

4% BUY + 4% SELL 对应约 **+8.33% 市场价回本带**。

我同意“小幅方向正确没有经济意义”。

但不同意直接把：

> “寻找具有 +15%～30% 潜在 impulse 的状态”

落成策略门槛。

因为“潜在 +15%～30%”本身是未来结果语言。

可部署规则必须翻译成**当时可观测状态**，例如：

- 已经产生跨越成本带的位移；
- 新价格区持续被独立帧接受；
- 活动/成交没有同步消失；
- liquidity 没有明显恶化。

不能设计一个事前并不存在的“未来还能涨 20%”变量。

---

## 4.4 限定 Microstructure 对 amountful flow 的优先级

真实净流、金额广度当然比 tx count 更接近经济机制。

但完成后的证据继续显示：

- 完整 flow 窗口并非全覆盖；
- 热池有限签名可截断；
- 地址不等于人；
- migration/flow 只在部分 surface 有真实输入。

所以 amountful-flow 候选可以存在，但：

> **覆盖不足时必须 WAIT，而不是回退成 count/volume 后仍沿用“真实净流策略”的名字。**

---

## 4.5 不赞成 ADVERSARIAL_RISK 的完整 entry×exit factorial 落地

反方 R1 建议做 entry/exit 拆解，这个统计原则是对的。

但如果工程上直接：

`8 entry × 5 exit = 40 arms`

会再次制造严重 correlated-arm explosion。

我的裁决是：

> 每个新 entry 只绑定一个预指定标准 exit，并最多配置一个 exit challenger；反过来，退出机制只在一个或极少量共享 entry cohort 上成对比较。

做**局部 paired decomposition**，不做全笛卡尔积。

---

# 5. BONK 日期纠错

`R1_EXTERNAL_RESEARCH.md` 写：

> BONK：2022-12-08

但完成后的 `EXTERNAL_EMPIRICAL_EVIDENCE.md` 已重新依据独立原始/公开来源整理，并记录：

> CoinGecko 研究口径为 **2022-12-25 发布**，2023-01-02 首 8 天 +305.8%。

因此：

**R2 不沿用 R1 External 的 2022-12-08 日期。**

R1 中那些 `turn...` 内部 citation 也不能作为最终项目 URL 证据。

最终外部材料应以 `EXTERNAL_EMPIRICAL_EVIDENCE.md` 中已经解析成原始公开 URL 的来源为准；若日期仍存在“mint/create / distribution / public launch / CoinGecko launch”口径差异，应分别保存字段，不能选一个日期强行称“唯一发布日期”。

---

# 6. 原 8 个已有代表逐项裁决

| 已有机制 | R2 | 小额 Paper | 原因 |
|---|---|---|---|
| 1. `l0_continuation_failure_candidate_v1` | **KEEP** | **YES，继续现有，不复制** | 91 paired 中 +21.79U 相对少亏；仍整体亏损，只是值得证伪的退出线索 |
| 2. `l0_profit_lock_candidate_v1` | **DROP FROM CORE / KEEP AS CONTROL** | 已存在可继续观察，不新增复制 | 59 paired 为 -62.54U；当前实现已有负反证 |
| 3. `observed_cycle_reset_reacceleration_v1` | **KEEP** | **YES，条件型** | 真正 sequence/episode 机制；必须尊重最多80帧/20min历史限制 |
| 4. `volatility_scaled_depth_flow_momentum_v1` | **KEEP WITH RENAME/SEMANTIC LIMIT** | **YES** | 有行为差异；所谓 pressure 只是聚合量代理，不能写成真实订单流 |
| 5. `experiment_participation_candidate_v1` | **CONDITIONAL** | **仅覆盖充分时 YES** | 地址扩散有机制意义，但 address≠person，覆盖不足不能补值 |
| 6. migration amount absorption | **CONDITIONAL KEEP** | **YES on supported surface only** | 生命周期机制不同；必须真实 migration + amount evidence，不能“迁移即买” |
| 7. `clone_liquidity_leader_v1` | **CONDITIONAL KEEP** | **YES** | 同题材多地址竞争值得研究；必须在 t0 冻结全集，不能事后挑赢家 |
| 8. `observed_set_relative_resilience_candidate_v1` | **KEEP** | **YES** | 相对选择与单币 momentum 正交；但只叫 observed-set relative，不冒充全市场 regime |

所以现有 8 个中：

- 6 个可留；
- 1 个条件较强；
- `l0_profit_lock` 不应占最终核心名单名额。

---

# 7. 新 8 个机制逐项裁决

## N1 突破后接受

**KEEP，但优先复用/升级现有 breakout family，不应机械新增重复 ID。**

逻辑有价值：

`明显位移 → 新价格区持续两个独立帧`

它与单帧 momentum 不同。

但项目已经存在：

- sustained breakout；
- mature acceptance；
- breakout/reclaim 等。

Codex 应先对行为合同做 hash/实际判断比较。

如果现有 arm 已经实现同一状态转换：

**MERGE，不再注册。**

如果现有只是斜率持续，而新机制明确要求：

> 跨成本后的 price-zone acceptance

则允许独立 5U challenger。

---

## N2 窄幅压缩释放

**MERGE。**

与历史：

- quiet → breakout；
- flat-compression-breakout observer；
- reawakening；

高度同族。

不值得再创建另一个“压缩后突破”名字。

建议最终只留一个：

**compression → expansion**

机制。

---

## N3 回测区域承接

草案里的“回测区域”应改名，避免和 backtest 混淆。

建议：

**突破区回踩承接 / retest acceptance**

裁决：**MERGE WITH reclaim/support family。**

项目已有：

- pullback reclaim；
- panic reclaim；
- support；
- reawakening recovery。

“两次保持后重新起步”可以作为该 family 的新版本条件，但不应作为第 16 个独立经济思想。

---

## N4 抛压减弱反弹

**KEEP，但必须改语义。**

当前可用的是：

`sell count share`

不是 sell amount。

所以不能叫“真实抛压减弱”。

建议命名：

**activity-asymmetry rebound / sell-count-share easing rebound**

机制：

- 急跌；
- 新低不继续扩大；
- sell-count share 下降；
- liquidity 保持；
- 后续价格收复。

它是低成本、可证伪、与单纯 reclaim 有一定差异的 L0 机制。

允许 5U Paper。

---

## N5 双次下探吸收

**MERGE / DROP AS SEPARATE STRATEGY。**

它和：

- retest acceptance；
- support；
- reclaim；
- panic recovery；

过度同质。

而且当前没有订单簿/真实被动挂单证据，因此“吸收”这个名字也过强。

最多成为 reclaim family 的一个状态版本，不占独立最终名单。

---

## N6 流动性先增后重估

**CONDITIONAL KEEP。**

这是较有价值的正交机制：

`price approximately flat → reported original-pool liquidity rises → price later confirms`

但有一个必须解决的解释问题：

> Dex/聚合器的 USD liquidity 本身可能随 token price 变化，因此 liquidity 与 price 不是天然独立变量。

草案要求 price 先基本平，已经部分缓解。

部署前应固定：

- 允许的价格变化带；
- liquidity growth 的最小持续帧数；
- 必须原池；
- missing/429 不填。

不能叫“LP 净存入”，除非真的看到 LP 事件。

允许条件型 5U Paper。

---

## N7 首冲后缩量再启动

**MERGE WITH `observed_cycle_reset_reacceleration_v1`。**

两者本质都是：

`impulse → cooling/reset → renewed activity`

区别不足以产生新的核心 strategy ID。

可以把“缩量整理且价位保持”作为 cycle-reset 的一个更明确新版本 challenger，但不应同时保留两个几乎相同名字。

---

## N8 阶梯式趋势持有

**不要作为独立 entry strategy。**

它本质主要是：

> 已经持有后，是否因为出现 higher-low / second leg 而允许继续持有。

历史的 conditional runner 当前 paired 结果 **-84.84U**，已经对“多拿一会儿”提出警告。

因此：

**RECLASSIFY → EXIT/HOLD CHALLENGER**

只能在同 entry cohort 上比较：

- normal exit；
- staircase-hold exit。

不要再包装成新选币 alpha。

允许未来 5U/同入场 paired Paper，但不进入当前首批新 entry 部署。

---

# 8. 八个新机制最终压缩结果

原拟 8 个，我建议压缩为真正独立的 **4–5 个**：

1. **cost-cleared breakout acceptance**
   若现有 breakout 合同不等价才新增。

2. **activity-asymmetry rebound**
   低成本 count-share 代理版本。

3. **liquidity-lead repricing**
   条件型。

4. **retest/reclaim family 的新版**
   将“回踩承接 + 双次下探”合并，只保留一个。

5. **staircase hold exit challenger**
   只作为退出 treatment，不算新的 entry alpha。

以下不再单列：

- compression release → 合并 quiet/compression；
- first-impulse cooling restart → 合并 cycle reset；
- double-bottom absorption → 合并 reclaim。

这样比强行凑 16 个更符合本轮“机制多样性”的目标。

---

# 9. 我建议最终 10–20 名单如何组成

建议 Codex 最终冻结约 **12–14 个经济机制**，而不是 16 个刚好凑数。

一个合理结构是：

### 高召回 / 凸性

1. Broad/high-recall baseline
2. Cost-cleared breakout acceptance
3. Volatility-scaled momentum

### 快速淘汰 / 退出

4. Continuation-failure exit
5. Cost-cleared peak/drawdown profit preservation
6. Staircase-hold challenger（只作 paired exit）

### 反转 / 第二波

7. Reclaim/retest acceptance
8. Activity-asymmetry rebound
9. Cycle reset / reacceleration

### 相对选择

10. Clone episode leader
11. Observed-set relative resilience

### 生命周期 / 流动性

12. Migration absorption
13. Liquidity-lead repricing / liquidity survival

### 稀疏结构证据

14. Participation breadth / event-wallet confirmation
仅在真实覆盖可用时运行。

这是比“8 老 + 8 新”更干净的机制组合。

---

# 10. 哪些底层事实会直接污染候选，必须先服从

只列本轮已有具体证据的，不要求大重构。

### 必须保留的硬边界

1. **original pool identity**
2. 正价但 `liquidity=NULL` 不是完整成功
3. stale/failed/429 不代表池死亡
4. 负 liquidity 不是“达标”
5. duplicate frame 不能冒充两个独立确认
6. observed/ingested 时间必须早于 decision
7. 不允许 sibling pool 替代原池
8. 一个账户/策略复制同 Token 不增加独立 N
9. flow 输入不完整时不能降级后仍叫 amountful-flow
10. migration/wallet/participation 缺输入就是 WAIT/coverage，不是失败币

这些是候选部署前必须继承的已有正确合同，并非要求建设新平台。

---

# 11. 资源与时序限制

根草案“新 L0 不新增外部请求”是正确的，建议保留。

### L0 新候选允许

复用同一次：

- price
- original-pool liquidity
- volume
- tx/buy/sell count
- 最多 80 帧
- 最长约 20 分钟已有观察

不要为了 N2/N3/N5 再增加新的采集器。

### 条件型候选

以下只能在已有数据真正存在时工作：

- participation breadth
- migration amount
- wallet/common funding
- actual net flow

不允许同步请求阻塞持仓退出。

### RH

外部共同证据明确：

Robinhood 当前主网本身是真实存在，但本轮没有足够 Meme 历史 ordinary/winner denominator。

所以新机制不应因为 SOL/BSC 成立就自动复制到 RH 并合并统计。

---

# 12. 小额 Paper 是否允许

**YES。**

但我建议冻结以下实验合同：

- 新 entry 机制：默认 **5U**
- 最多同时 **4 仓**
- 新 ID 只在确有行为差异时创建
- 新 deployment frontier
- 不回填
- 不重置当前 206 或历史账户
- 不关闭旧策略
- baseline/control 同时保留
- 每个 entry 最多一个主 exit + 一个 exit challenger
- 不生成 entry×exit 笛卡尔积
- missing/UNKNOWN 保留
- 按 `token/pool/cohort/episode` 聚类报告
- 当前 1.29h 统计只作为 hypothesis-generation evidence

### 不允许小额 Paper 的具体情况

不是“没有 alpha”，而是以下情况才 BLOCK DEPLOYMENT：

1. 规则事实上与现有 arm 等价；
2. 依赖字段当前根本没有可靠输入；
3. 需要未来 ATH/未来 winner 才能定义；
4. 输入缺失时需要伪造默认值；
5. 必须新增会显著抢持仓/退出资源的外部采集；
6. 同一机制只是阈值变化；
7. 无法冻结 baseline；
8. 不具备新 frontier / point-in-time 语义。

这和 **BLOCK ALPHA CLAIM** 是两个完全不同的门。

---

# 13. 统计与晋级建议

当前不要做显著性宣称。

首先积累新的 unique episodes。

建议至少继续报告：

- unique token/episode N
- closed / open / right-censored
- dates
- candidate-control paired delta
- total
- median
- trimmed mean
- P05 / tail
- win rate
- writeoff / no-route / unknown
- Top1 / Top3 contribution
- remove-best-1
- remove-best-3
- remove-best-token-1/3
- regime/date block
- contamination denominator
- input coverage

尤其注意已经完成的全历史统计证明：

> **“移除最佳三笔”可能仍然漂亮，但按 token 聚类移除赢家后会直接翻负。**

v22 就是典型：

- headline +7.316M U
- 单一 token 占正 token PNL **94.14%**
- remove-best-token-1 → **-232,664U**
- remove-best-token-3 → **-554,672U**

所以最终候选的 winner-removal 必须以 **token/episode** 为主要 robustness，而不是只删三笔账户交易。

---

# 14. 外部证据应如何使用

完成后的外部研究支持以下机制假设：

- demand/breadth continuation；
- manipulation-aware activity；
- early risk transitions；
- migration/lifecycle；
- same-narrative competing mints；
- mature-token reawakening；
- creator history作为软风险；
- liquidity deterioration before price。

但外部十二个具名案例仍然是**目的性案例集，不是普通币分母**。

不能：

> BONK/WIF/TRUMP 都有某特征 → 所以这个特征有 alpha。

完整 ordinary/failed/crash control 必须继续依赖本地统一 denominator 的前向特征研究；`TOKEN_PRECURSOR_EVIDENCE.md` 仍在进行，本轮不抢跑结论。

---

# 15. 给 Codex 的最终 R2 建议

**允许部署研究型候选，但先去重。**

不要把 16 个草案机械全上。

我建议：

- 保留现有真正非等价代表；
- `l0_profit_lock` 降级为已有 comparator；
- 合并 compression/cycle-reset；
- 合并 retest/double-dip/reclaim；
- staircase 从 entry 改成 exit treatment；
- breakout acceptance 先查与已有 breakout/mature-acceptance 是否行为等价；
- 新增最多约 3–5 个确实新的 L0 treatment；
- wallet/migration/participation/liquidity-lead 作为 coverage-conditioned arms；
- 总核心机制最后约 **12–14 个**即可。

**BLOCKS PROFIT CLAIM：YES。**
**BLOCKS LIVE/CAPITAL PROMOTION：YES。**
**BLOCKS SMALL STRICT-FORWARD PAPER：NO。**

当前最有价值的目标不是证明我们“已经找到赢家”，而是用下一段自然市场数据把这些彼此正交的假设尽快杀掉一部分。这样剩下来的机制，才值得进入 R3 的终极组合。
