# R2 ADVERSARIAL_RISK

Source Chat: 6a9d94dd-2eb8-83e8-ac4b-bdfc14bd49a1
Actual response; model setting not independently verified. Markdown trailing whitespace normalized.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R2-ADVERSARIAL_RISK-RESULT
REPLY_TO: C2C-20260907-R2-ADVERSARIAL_RISK
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: ADVERSARIAL_RISK
DISPOSITION: **PROCEED_BOUNDED_PAPER / BLOCK_ALPHA_PROMOTION / REVISE_16_TO_12-13_MECHANISMS**
BLOCKS_RELEASE: true
MODEL: GPT-5.6 Sol；推理档位未由项目侧独立核验。
SENSITIVE_DATA: NONE

## 一、R2 总裁决

完成交叉阅读后，我修改 R1 的一个重要倾向：

**我仍然阻止任何盈利/alpha 宣称，但不再支持把这种阻止自动扩展成“禁止候选进入小额 Paper”。**

冻结统计已经相当明确：

- 当前最终期只有 **1.28936 小时**；
- 6,681 个闭环合计约 **-40,134U**；
- 胜率 **17.00%**；
- PF **0.231**；
- expectancy **-6.01U**；
- median **-4.16U**；
- 1,932 个 WRITEOFF 仍只是 Paper 核销，不是实际链上卖出；
- 当前唯一闭环总 PNL 为正的 arm 只有约 **+4.83U**，去掉最佳三笔后已经约 **-29.61U**。

这些数字足以说：

> **没有已验证 alpha。**

但它们不足以说：

> **所有新机制都不值得再做 5U 严格前向实验。**

相反，历史统计最大的价值，就是帮助我们**删掉重复机制、降低错误优先级、构造更干净的前向对照**。

---

# 二、冻结统计对 R1 风险判断的最终验证

## 1. v22 的“漂亮历史”确实被击穿

这是我 R1 最关心的问题，现在已经有冻结统计回答。

v22：

- 闭环 PNL：约 **+7.316M U**
- 中位数：**-1.54U**
- 正闭环仅 **5.27%**
- 单一 token 占正 token PNL **94.14%**
- 前三个 token 占 **98.16%**
- 去掉最大一个 token 后：**-232,664U**
- 去掉前三 token 后：**-554,672U**

所以这是非常典型的：

**账户复制 + 极端右尾 token + 非受约束研究资金模式**

共同制造的漂亮累计 PNL。

这一项现在无需再争论：

**v22 不具备 alpha 晋级资格。**

但不能由此推出“右尾捕捉没有价值”。正确结论是：

> Meme 的右尾极其重要，但必须在 token/cohort 聚类后验证，而不是靠重复账户放大同一个赢家。

---

## 2. v19 不能因为更稳一点就晋级

v19：

- 原闭环约 +398k；
- 去最大 token 后仍约 +279k；
- 去前三仍约 +154k。

表面上比 v22 健壮很多。

但历史地图明确记录了 v19 的：

**legacy Jupiter exit raw-decimal contamination**。

因此这个结果属于：

**interesting historical anomaly / not decision eligible**，

而不是候选 alpha 证据。

---

# 三、我与其他 R1 至少三处不同意见

我实际交叉阅读了：

- `R1_STRATEGY.md`
- `R1_MICROSTRUCTURE.md`
- `R1_CAUSAL_STATISTICS.md`

以下不是简单附和。

---

## 分歧 1：不赞成把 “Peak/drawdown exit” 单独占一个最终策略名额

`R1_STRATEGY` 将：

> peak/drawdown single-wave exit

列入约 14 个最终方向。

我认为这更适合作为**共享退出 treatment**，而不是独立经济策略。

原因是历史已经反复暴露：

- 同一个 entry 配不同 exit；
- 同一个 cohort 投影到多个账户；

会非常容易制造“策略数量”。

所以应采用：

**entry mechanism × 少量预注册 exit challenger**

而不是把每种 exit 都算一个“终极策略”。

我支持 peak/drawdown 继续研究，但**不支持它单独占最终机制数**。

---

## 分歧 2：不赞成 Microstructure R1 的 “+15%～+30% potential impulse” 作为规则目标

`R1_MICROSTRUCTURE` 提议 Cost-Clearing Impulse 应瞄准 +15%～+30% 级 impulse。

它的经济出发点正确：双侧 4% 的 Paper 回本带约 **+8.33%**。

但我反对把：

> +15%、+20%、+30%

快速固化成新 entry gate。

原因：

1. 当前本地 precursor 研究尚未完成；
2. 这些数字不是冻结统计选出的稳定边界；
3. 极容易重新滑回 threshold spray；
4. 事后知道某币能涨 30% 和 t0 能识别 30% impulse 是两回事。

正确应用方式应该是：

**候选的结果目标必须跨过成本带，不能把“小涨正确”称作经济成功；但 entry 本身不应因此直接设成预测未来 +15/+30%。**

---

## 分歧 3：我比 Strategy R1 更倾向缩减新 ID 数量

`R1_STRATEGY` 倾向 10–14 个行为方向，我赞成数量范围，但根草案里的很多“新机制”其实已有祖先。

冻结历史地图现在明确发现已有：

- `flat_compression_breakout_shadow`
- `mature_acceptance`
- `pullback_reclaim`
- `panic_reclaim`
- `cycle_reset`
- `quiet_reawakening`
- `conditional_runner`
- `observed_set_relative_resilience`
- clone leader/handoff

因此 R2 不应该因为名称更漂亮就重新注册。

**能复用旧 ID / family 的必须复用；只有真正改变状态机时才新增 ID。**

---

# 四、对根草案 8 个已有代表逐项裁决

| 现有机制 | R2裁决 | 小额Paper |
|---|---|---|
| `l0_continuation_failure_candidate_v1` | **KEEP，作为退出 challenger**。当前 paired intersection 91 个，candidate-control +21.79U，但两边仍整体亏损；只支持“少亏线索”。 | **YES**，继续严格配对；不宣称 alpha |
| `l0_profit_lock_candidate_v1` | **KEEP AS MODULE，降优先级**。当前同 cohort 差 **-62.54U**，不能因“锁利”听起来合理就推广。 | **YES，但只能 paired exit experiment** |
| `observed_cycle_reset_reacceleration_v1` | **KEEP CONDITIONAL**。机制正交；但 80 帧/20分钟历史限制必须真实满足 reset 序列。 | **YES，5U** |
| `volatility_scaled_depth_flow_momentum_v1` | **KEEP BUT RENAME SEMANTICS**。所谓 pressure 只是 L0 聚合代理，不是真 depth/amount flow。 | **YES，5U** |
| `experiment_participation_candidate_v1` | **KEEP CONDITIONAL**。地址扩散有机制差异，但 address≠person，缺解析覆盖不能填。 | **YES，仅覆盖充分 surface** |
| migration amount absorption | **KEEP CONDITIONAL / HIGH VALUE**。生命周期状态转换与普通 momentum 不同。 | **YES，5U；只在 exact migration + amount 覆盖成立时** |
| `clone_liquidity_leader_v1` | **KEEP / HIGH PRIORITY**。天然 contemporaneous control，统计结构非常干净。 | **YES，5U** |
| `observed_set_relative_resilience_candidate_v1` | **KEEP**，但必须和 clone leader 区分：这是 broader observed set relative state，不是同叙事 clone ranking。 | **YES，5U** |

结论：

**已有 8 个不需要全部删。**

但真正适合最终“机制代表”的大约 6–7 个，因为 `profit_lock` 更像 exit module。

---

# 五、对 8 个拟新增机制逐项反驳、删并

这是本轮最重要的部分。

## N1 突破后接受

**裁决：REUSE / MERGE，不新建 ID 优先。**

机制本身有价值：

> 跨成本突破 → 不立即追 → 新价格区被后续独立帧接受。

但当前历史谱系已经存在：

- mature acceptance；
- sustained breakout；
- breakout 类 L0；
- price acceptance 类观察。

因此先核对现有 `mature_new_acceptance` / breakout 行为 hash。

只有如果根草案真的增加：

**“跨成本位移 + 独立价格区 acceptance state”**

且旧实现没有，才允许新 ID。

**Paper：YES，5U。**

---

## N2 窄幅压缩释放

**裁决：REUSE EXISTING SHADOW / NO DUPLICATE PAPER ID。**

项目已经有：

`flat_compression_breakout_shadow`

以及 V002 的 compression 类 L0 替代。

所以目前不需要第三次重命名成“窄幅压缩释放”。

先把现有 Shadow 的：

- coverage；
- baseline completeness；
- false breakout；

做前向转化。

**Paper：目前建议 CONDITIONAL。**
如果现有 shadow 已有足够 t0 coverage，则新增一个 5U treatment；否则继续 Shadow。

---

## N3 回测区域承接

这个名称本身容易误导，实际是：

**breakout → healthy pullback → retest hold → reacceleration**

**裁决：MERGE WITH pullback_reclaim。**

它和现有 `pullback_reclaim` 在经济机制上太近。

“两次保持”只是状态确认细化，不足以自动升级成新经济思想。

若新增只是：

一次确认 → 两次确认，

这是参数/确认强度变体，不应占最终名额。

**Paper：复用 parent candidate/control，NO 新 ID。**

---

## N4 抛压减弱反弹

**裁决：KEEP AS NEW L0 MECHANISM，但必须改名。**

当前可观察的是：

- sell count share；
- price lows；
- liquidity；
- volume。

没有真实 sell amount 时，不能叫：

“卖压金额衰减”。

建议准确表述：

**sell-activity-share decay rebound**

或者中文：

**卖方成交占比衰减反弹**。

它和 panic reclaim 的区别应被冻结：

- panic reclaim：价格结构；
- 新 candidate：价格结构 + 卖方活动占比持续下降。

若实际行为 hash 最后没有差异，则合并。

**Paper：YES，5U。**

---

## N5 双次下探吸收

**裁决：DELETE / MERGE。**

它和：

- pullback reclaim；
- support risk；
- N3 retest hold；

高度重叠。

“两次低点不破”听起来是新图形，本质仍是：

**support/retest state persistence**。

没有订单簿/真实吸收数据，也不能叫“吸收”。

建议完全删除独立 ID，将“第二次 retest”作为 `pullback_reclaim` 的可选状态版本，而不是终极机制。

**Paper：NO NEW DEPLOYMENT。**

---

## N6 流动性先增后重估

**裁决：GOOD IDEA / SHADOW FIRST。**

这是 8 个新方案中我比较喜欢的一个，但现在不建议直接 Paper。

最大反方问题：

Dex/Gecko 的 `liquidity_usd` 可能同时受到：

- token price；
- reserve mark；
- provider calculation；
- pool composition；

影响。

所以看到：

`price flat + liquidity_usd ↑`

不一定意味着 LP 真注入资金。

必须先证明该指标的变化不是仅由价格/报价单位机械产生。

**部署：先 Shadow。**

只有确认：

- 原池 identity；
- liquidity 字段连续；
- change 不是 provider artifact；
- baseline 足够；

才进入 **5U Paper**。

因此这里属于：

**BLOCK PAPER CURRENTLY，NOT BLOCK RESEARCH。**

---

## N7 首冲后缩量再启动

**裁决：MERGE WITH CYCLE RESET / REAWAKENING。**

它与现有：

`observed_cycle_reset_reacceleration`

高度同源：

> impulse → cooling/reset → renewed activity.

没有必要再造 ID。

如果它强调：

- price retains level；
- volume cools；
- activity reaccelerates；

那么这些是 cycle-reset 的状态定义，不是新经济机制。

**Paper：继续现有 cycle-reset candidate。**

---

## N8 阶梯式趋势持有

**裁决：EXIT CHALLENGER ONLY / NO NEW ENTRY STRATEGY。**

这本质不是新入场机制，而是：

> 已有赢家是否因为形成 higher-low sequence 而值得延长持有。

当前历史却给了强烈反证：

`experiment_conditional_runner`

paired intersection 108：

candidate 相对 control **-84.84U**。

所以“走势看起来还健康，多拿一会儿”当前并没有好的自然先验。

并非永久否决，但如果继续，只能：

**同 entry paired exit challenger / 5U**

且必须提前定义失败条件。

不能作为独立“终极策略”。

---

# 六、16 个草案应缩成什么

我的 R2 建议不是 16 个全部保留。

### 应形成约 12–13 个真正不同的机制

1. **Broad high-recall + continuation-failure triage**
2. **Cost-cleared profit preservation**
   profit-lock/peak decay 归为一个退出研究族
3. **Cycle-reset / reacceleration**
4. **Volatility-scaled L0 momentum**
5. **Participation expansion**
6. **Migration absorption**
7. **Clone-set leader selection**
8. **Observed-set relative resilience**
9. **Price-zone acceptance / mature acceptance**
10. **Compression breakout**
   优先 Shadow→Paper，不重复 ID
11. **Pullback/retest reclaim**
12. **Sell-activity-share decay rebound**
13. **Liquidity-first revaluation**
   目前 Shadow-only

另外：

- double-dip absorption → **删除**
- first-impulse cool/restart → **并入 cycle reset**
- staircase hold → **退出 challenger，不占 entry 机制名额**

这样比 16 个名称更干净。

---

# 七、资源与时序约束

这里我同意 Data/Engineering 风格的保守边界，但不要求新平台。

## 可以低成本直接支持的

使用现有最多 80 帧/20 分钟的原池序列即可：

- acceptance；
- reclaim；
- continuation failure；
- sell-count-share decay；
- volatility normalized momentum；
- short cycle reset；
- relative resilience。

这些都不应增加外网调用。

---

## 有严格覆盖限制的

### Participation

必须实际有已解析地址。

`tx count` 不能替代 unique buyer。

### Migration absorption

必须：

- exact migration；
- 当时 protocol/surface identity；
- amount evidence。

无法覆盖时 WAIT，不造“迁移后吸收”。

### Cycle reset / quiet reawakening

80 帧仅覆盖约 20 分钟时：

不能宣称识别数小时静默。

短 reset 与长期 reawakening 应区分。

### Liquidity-first

必须先确认 `liquidity_usd` 变化语义。

### Clone leader

候选集必须在 t0 冻结。

不能到 t+60m 才把最后胜者补进 candidate set。

---

# 八、BONK 日期纠错

用户特别要求这项不能沿用 Chat citation。

我重新直接核查了外部网页。

BONK 官方当前 About 页面写的是：

> launched on Christmas Day

即 **2022-12-25**。citeturn401564search2

CoinGecko 的原始研究页也明确写：

> launch on December 25, 2022

并记录 2023-01-02 为 launch 后第 8 天达到 +305.8%。citeturn401564search0

因此本轮应以 **2022-12-25** 作为当前核验到的公开发行日期。

如果某份独立报告给出不同日期：

**保留 source disagreement，不把该报告日期覆盖官方/直接研究来源。**

同时这仍然只是历史案例身份/时点核验，**不得作为本地策略输入证据**。

---

# 九、阻止盈利宣称与阻止候选部署必须严格区分

## A. 以下只阻止 **盈利/alpha 宣称**

这些机制我允许小额 Paper：

- continuation failure；
- profit preservation；
- cycle reset；
- volatility-scaled L0；
- participation（覆盖充分时）；
- migration absorption（覆盖充分时）；
- clone leader；
- relative resilience；
- mature acceptance；
- reclaim；
- sell-activity decay rebound。

共同条件：

- 新 frontier；
- 5U 优先；
- 不重置旧账户；
- 保留 control；
- next independent original-pool frame；
- 失败/UNKNOWN 留分母；
- 不用当前前置特征研究的未完成结果调阈值。

---

## B. 以下目前连新 Paper ID 都应阻止

### 1. 完全等价旧机制的新名字

例如：

- N5 双次下探吸收；
- N7 首冲缩量再启动；
- 现有 compression 的重复注册。

原因：

**没有新经济 treatment，只增加多重选择。**

### 2. Liquidity-first revaluation

当前应：

**Shadow first**

直到 liquidity 变化语义确认。

原因不是机制不好，而是输入解释仍可能错。

### 3. 任意依赖未完成 `TOKEN_PRECURSOR_EVIDENCE.md` 结果定参数的新策略

当前本地前置研究仍进行中。

不得提前声称：

- 哪个 winner precursor 显著；
- 哪个阈值好；
- 哪个变量预测 alpha。

---

# 十、小额 Paper 的推荐合同

我支持根草案：

- **5U**
- 同一新机制最多 **4 个同时开放仓**
- strict-forward
- 不回填
- 不自动重置
- 不改旧策略
- 不启用 Live

另外增加四个约束：

1. **每个机制只注册一个主 candidate。**
2. 有自然父策略时保留一个 control，不做多阈值矩阵。
3. 分析单位默认 token/pool/cohort，而非账户笔数。
4. 对新 entry 首先评价：
   - coverage；
   - opportunity count；
   - false-positive cost；
   - 下尾；
   - remove-top-token；
   - paired delta；

   再看累计 PNL。

---

# 十一、R2 对“最终策略组合”的建议

目标不应是找到 10 个历史排行榜冠军。

应该覆盖不同收益生成机制：

**高风险凸性**
- Broad+fast triage
- Volatility impulse

**稳健确认**
- Mature price acceptance
- Compression release

**反转/复苏**
- Pullback reclaim
- Cycle-reset/reacceleration
- Sell-activity decay rebound

**相对选择**
- Clone leader
- Relative resilience

**结构生命周期**
- Migration absorption
- Participation expansion

**退出控制**
- Continuation failure
- Profit preservation

这大约 **13 个 mechanism families**，已经达到用户要求的 10–20，并明显比 16 个草案更少同质化。

---

# 十二、实际读取路径

本轮实际读取：

- `docs/PROJECT_CONTEXT/RESEARCH_2026-09-07/R2_DESIGN_QUESTIONS.md`
- `.../HISTORICAL_STATISTICS.md`
- `.../HISTORICAL_EVIDENCE_MAP.md`
- `.../EXTERNAL_EMPIRICAL_EVIDENCE.md`
- `.../R1_STRATEGY.md`
- `.../R1_MICROSTRUCTURE.md`
- `.../R1_CAUSAL_STATISTICS.md`
- `AGENTS.md`

没有运行大 SQL，没有写 Runtime/DB/代码，没有读取 secret。

---

## FINAL R2 ADVERSARIAL JUDGMENT

**BLOCK_ALPHA_PROMOTION：YES。**

**BLOCK_ALL_RESEARCH_PAPER：NO。**

**ALLOW_BOUNDED_5U_FORWARD_PAPER：YES，针对约 11–12 个已有/可立即解释的机制。**

**SHADOW_FIRST：Liquidity-first revaluation，以及任何输入语义/覆盖尚未成立的机制。**

**NO_NEW_ID：与 existing acceptance / compression / reclaim / cycle-reset 完全等价的重命名方案。**

当前 1.29 小时统计证明的是：

> **当前组合表现很差，而且任何 alpha 声称都站不住。**

它没有证明：

> **机制研究应该停止。**

R3/Codex 应进一步把 16 草案压缩到约 **12–13 个真正经济正交的 family**，只为实际改变状态机的部分新增 ID；保持所有旧策略和历史，不重置，由 Codex 作为唯一 writer 最终裁决。
