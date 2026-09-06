# R3 DATA_ENGINEERING

Source Chat: 6a9d94c3-d250-83e8-9ef0-24d6498281ea

Actual response; model/reasoning not independently verified. Snapshot review, not deployment certification.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R3-DATA_ENGINEERING-RESULT
REPLY_TO: C2C-20260907-R2-DATA_ENGINEERING-RESULT
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: DATA_ENGINEERING
BLOCKS_RELEASE: true
SENSITIVE_DATA: NONE

**DISPOSITION: REVISE_THEN_DEPLOY_SMALL_PAPER / BLOCK_ALPHA_PROMOTION**

模型：GPT-5.6 Sol；**实际推理档位/宿主配置未核验**。

本轮按新 `FINAL_CONTRACT` 重新评审。R2“8复用+8新”结论**全部撤回为历史意见**；当前有效对象是 **5既有代表 + 3新entry + 4新exit = 12机制，另1共同exit baseline；实际只新增8账户**。

## 1. 总体结论

代码结构总体与最终合同相符：

- 新8账户append-only注册，同一时间激活；
- 不改旧206；
- 3 entry使用现有L0历史，不新增API；
- 5个exit账户显式 `paired_entry_size=5`；
- 5U、4仓；
- 后帧执行；
- NULL/负liq不通过；
- source/pool切换不拼序列；
- exit采用含买卖成本的 `economic_value_usd`；
- future/out-of-order/duplicate/stale frame已有公共 `_begin()` 拒绝。

**但我不建议以当前测试状态直接部署。发现1个数据证据缺口；另有1个必须补的实际接线验收。两者都是小修，不需要新平台。**

---

## 2. 5臂配对：交易层不会部分成交，但拒绝证据有缺口

### 已核验：不会因某臂槽位不足而只成交4/5

`store.py`先计算：

- 各arm `max_concurrent_positions=4`；
- 已占槽进入 `entry_blocked`；
- 然后配对组要求：

`expected == {len(arms)}` 且 **所有5臂都在 admitted_arms**

否则整组从 `admitted_arms` 删除。

现金也在真正project前逐臂检查；只要任一臂：

`starting_cash + net_flow < 5U + fee`

就把**整组5臂**从 `by_notional` 删除。

所以“某臂没钱/没槽→整组不进”的主要经济合同成立。现有三链测试也实际得到4个机会×5仓=20仓，第5个机会因4仓限制全组不进。

### 发现：现金导致整组拒绝时，没有逐臂 rejection row

槽位拒绝在 `entry_blocked` 中有明确原因。

但**paired cash check发生在建立 cohort / 写 `chain_meme_trader_entry_decisions` 之前**，只是从 `by_notional` 删除整组。因此这种机会可能只表现为最终 `projected=0`，没有5条明确：

`entry_cash_below_order_size / paired_group_cash_blocked`

这不影响资金安全，却会污染后续要求的：

- eligible denominator；
- per-arm reject reason；
- “零机会 vs 有信号但配对现金不足”的解释。

### 裁决

**最小必要修正后部署。**

不需要改配对算法，只需要确保paired cash整组拒绝有可查询的明确原因/分母。否则以后看到零BUY又会重新陷入“策略没信号还是账户没钱”的歧义。

---

# 3. 3个新entry

### `finalist_boundary_retest_v1`
**可部署小额Paper。**

代码确实是A冻结上沿→B突破→C回访旧边界→重新抬升，不是普通max-peak reclaim。身份、source、时间链均fail-closed。

反例测试也验证“根本没回踩，只一路涨”不会通过。

**解释限制：**不是“支撑位已被市场证明”，只是9帧L0状态序列假设。

---

### `finalist_seller_absorption_v1`
**可部署小额Paper。**

名称/合同现在已经正确克制：

- buys/sells只是笔数；
- 不称金额；
- 不称钱包；
- 不称smart money。

旧“participation=真实钱包扩散”的R2解释正式撤回；`EFFECTIVE_POLICY_CORRECTIONS`已经证明stage143实际是V002 L0代理。

**风险仅限证据解释，不阻止部署：**滚动m5窗口变化可能来自旧交易滚出，因此所谓“翻转”不是逐笔流向变化。

---

### `finalist_price_then_depth_v1`
**可部署小额Paper。**

这是R2里最需要纠正语义的一项：当前机制不是“流动性领先价格”，而是**价格先脉冲，随后同source报告liquidity追认**。代码与合同一致。

它明确拒绝B阶段liq已经先升的反例。

**只限证据解释：**

`liquidity_usd`不能解释为LP注资、净资金流或可执行深度；还存在价格计价和provider异步刷新耦合。部署没问题，宣传必须严格叫“reported liquidity confirmation”。

---

# 4. 四新exit + baseline

四个纯函数本身的时序/状态处理是合理的：

- future frame拒绝；
- duplicate拒绝；
- out-of-order拒绝；
- >15秒 stale拒绝；
- provider变化reset；
- >60秒gap reset；
- <5秒不累计；
- 无数据时间不会被progress clock当成180秒静默。

## `finalist_profit_budget_v1`
**可部署，但只解释为“公共退出之上的增量overlay”。**

净利润计算正确使用：

`realized proceeds + remaining qty × 当前Paper卖出净额 - stake`

不依赖那个已证不可达的 `principal_recovered/cost_covered`。

因此我R2引用 `l0_profit_lock -62.54U` 作为“正确L0锁利反证”的说法**撤回**。该旧实现根本没有接通回本状态，不能拿其负delta否定现在的新profit-budget机制。

但通用+30%后15% trailing可能先于该策略动作，合同也已明确承认。这不是bug；它意味着estimand是：

> 在公共stop/trailing/maxhold存在时，profit-budget还能否进一步改变退出。

不能宣传为纯粹单独profit-budget策略。

---

## `finalist_progress_clock_v1`
**可部署。**

实现确实不是“每帧必须+1%”，而是累计经济值超过锚点1% stake就刷新进展时钟。

数据断流/来源切换会重置clock，不会把API静默误判成市场横盘。

**解释限制：**reset会使真实无进展时间偏短，因此若表现差不能立即归因机制本身；需披露source-reset数量。

---

## `finalist_depth_divergence_v1`
**可部署。**

要求连续：

- price下降；
- economic value下降；
- liquidity每步>1%上涨。

与旧“liq不增长同时跌价”风险退出确实不同。

只能叫：

**reported liquidity up / price down divergence**

不能叫增LP、吸筹或深度改善。

---

## `finalist_activity_failure_v1`
**可部署。**

要求：

- price/economic value连续下降；
- buy-count share上升；
- rolling volume连续>2%增加。

代码没有把它误写成金额流或wallet flow。

**解释限制：**rolling m5量不是新成交delta，所以只表示供应商滚动活动指标继续增强。

---

# 5. 部署前必须补的一项接线测试

当前 `tests/test_research_finalists.py` 已覆盖：

- 3 entry正反例；
- dense sampling；
- future/duplicate/source切换；
- 4 exit纯函数；
- 成本数量；
- 三链next-frame entry；
- 5臂配对；
- 4仓上限；
- append-only注册。

但我实际读取的测试里**尚未看到Store级真实exit接线测试**证明：

`持仓 mark → _capital_exit_result → CAPITAL_EXIT pending mark → 下一独立原池帧fill`

分别对四个exit确实可达，并且baseline不触发该专属exit。

源码路由看起来已接：

`EXIT_KINDS → evaluate_finalist_exit → capital action`

但代码存在≠实际接线已验收。

### 裁决

**这是部署前的小型阻断项。**

补一个定向Store级测试即可，不需要大SQL、不需要全suite、更不需要另建执行系统。

---

# 6. 80帧与数据静默

### 新3 entry
9个≥15秒间隔帧，要求总跨度120–600秒。80帧容量原则上足够；dense sampling由反向挑选保证最新帧不被挤掉。

而且实现不是只检查选出的9帧：从第一个选中帧到当前的**所有实际history**都检查：

- causality；
- identity；
- provider；
- gap≤60秒；
- 完整L0。

因此不能删除中间坏帧“拼漂亮路径”。

### stage185 cycle
不同。它要求≥720秒，而observer只有最近80帧/20分钟；高频采样时80帧可能覆盖不到720秒。

所以：

**stage185继续运行可以，但只属于“覆盖待证条件型储备”。**

0 BUY不能解释为机制失败，更不能为了产生成交而缩短720秒。

---

# 7. 外部论文与本地precursor证据

外部v3纠错维持：

- 0.198%不是24h毕业率；
- wallet最新版资金增幅区间含0；
- placebo是偏差诊断；
- BONK t0未裁定。

所以12候选没有任何一个能借这些论文获得alpha加分。

本地 `TOKEN_PRECURSOR_EVIDENCE.md` 同样不支持阈值优化：

- universe 12k样本中只有101暴涨；
- chain框60m仅506 observed；
- chain暴涨vs失败没有一个冻结分层能两侧各≥3；
- marginal volume/buy-ratio/count差异受chain/time/provider/market regime严重混杂。

这反而支持当前做法：**新规则一次性预注册后重新前向，不把本地描述性差异拿来调参数。**

---

# 8. 与另一R2的实质分歧

我选择 `R2_CAUSAL_STATISTICS`。

它曾根据59个paired closure、`-62.54U`，把当前 `l0_profit_lock` 描述成对profit-lock机制的实际反证。

**R3不同意，且现在有源码级证据裁决。**

`EFFECTIVE_POLICY_CORRECTIONS.md` 和Store路由证明：

- `l0_profit_lock` evaluator要求 `principal_recovered or cost_covered`；
- 当前exit family并不会写入该状态；
- 93仓全部principal=0；
- 0次真正 `l0_two_frame_profit_lock`；
- 15次半卖只是TP行为。

所以：

`-62.54U`只能反映该旧candidate/control整体合同差异，**不能作为“正确实现的连续恶化profit-lock失败”证据。**

这也是当前新 `finalist_profit_budget_v1` 值得独立小额前向验证而不是被旧负delta直接否决的原因。

---

# 9. 最终分类

**部署前阻止：**
1. paired cash整组拒绝缺少明确逐臂/组级拒绝证据——最小修正；
2. 四新exit缺Store级实际接线验收——补一个定向测试。

**修正后允许5U Paper：**
- 3个新entry；
- 4个新exit；
- baseline；
- 既有190、187继续；
- 196条件型继续；
- 185、194只作为覆盖待证储备。

**只限制解释、不阻止部署：**
- rolling volume/count并非真实资金流；
- liquidity_usd并非LP/depth；
- generic stop/trailing可能先于新exit；
- provider reset会改变有效观察时长；
- cycle/clone低覆盖；
- 当前Paper仍是轻量mark±成本，不是实盘可执行收益。

**继续BLOCK：**
- alpha/长期盈利；
- 放大资金；
- Live；
- 用测试结果冒充自然结果；
- 用13个重点账户称13个独立市场样本。

## 实际读取路径

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/FINAL_CONTRACT.md`
- `.../EFFECTIVE_POLICY_CORRECTIONS.md`
- `.../TOKEN_PRECURSOR_EVIDENCE.md`
- `.../EXTERNAL_CORRECTIONS.md`
- `.../R2_CAUSAL_STATISTICS.md`
- `.../R2_ADVERSARIAL_RISK.md`
- `src/memetrader/research_finalists.py`
- `src/memetrader/capital_exits.py`（`_begin`必要段）
- `src/memetrader/store.py`（注册、slot、paired admission/cash、finalist exit adapter、通用exit优先级必要段）
- `tests/test_research_finalists.py`
- `AGENTS.md`

未运行大SQL、未修改代码/DB/Runtime、未读取secret、未部署。

**R3 DATA_ENGINEERING：`REVISE_THEN_DEPLOY_SMALL_PAPER`。** 核心设计已经足够收敛，不需要再造系统；解决上述两个很小但会影响证据真实性/实际可达性的点后，我不支持继续用审查拖延严格前向实验。
