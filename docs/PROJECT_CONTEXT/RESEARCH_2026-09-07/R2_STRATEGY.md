# R2 STRATEGY

Source Chat: 6a9d94a3-6898-83e9-b5ce-9c598543fabf
Actual response; model setting not independently verified. Markdown trailing whitespace normalized.

[GXH_C2C_V3]
MESSAGE_ID: C2C-20260907-R2-STRATEGY-RESULT
REPLY_TO: C2C-20260907-R2-STRATEGY
TYPE: RESULT
CYCLE_ID: ALL_HISTORY_20260907
ROLE: STRATEGY
BLOCKS_RELEASE: true
DISPOSITION: **REVISE / ALLOW_BOUNDED_SMALL_PAPER / BLOCK_ALPHA_PROMOTION**
SENSITIVE_DATA: NONE

本轮已实际通过 `笔记本量化MCP-官方隧道` 只读访问 `E:\memeTrader`。未写代码、Runtime、数据库，未跑大SQL。实际重点读取了：

- `RESEARCH_2026-09-07/R2_DESIGN_QUESTIONS.md`
- `RESEARCH_2026-09-07/HISTORICAL_STATISTICS.md`
- `RESEARCH_2026-09-07/EXTERNAL_EMPIRICAL_EVIDENCE.md`
- `RESEARCH_2026-09-07/R1_ADVERSARIAL_RISK.md`
- `RESEARCH_2026-09-07/R1_CAUSAL_STATISTICS.md`
- `RESEARCH_2026-09-07/R1_MICROSTRUCTURE.md`
- 并核对了 `R1_EXTERNAL_RESEARCH.md` 中 BONK 的冲突字段。

本地 `TOKEN_PRECURSOR_EVIDENCE.md` 尚在研究中，本结果**不预判、不引用其未完成结论**。

## 一、先冻结统计事实：目前没有alpha晋级资格

`HISTORICAL_STATISTICS.md` 把R1阶段的一些模糊风险变成了明确反证。

最终资金期截至统计切点只有 **1.28936小时**。虽然有6,681个闭环，但它们绝不能解释成6,681个独立市场实验：

- 闭环 PNL `-40,134.18U`
- 胜率 `17.00%`
- PF `0.231`
- expectancy `-6.01U`
- median `-4.16U`
- P05 `-20U`
- P95 `+13.66U`
- 1,932次WRITEOFF仍只是Paper终止语义，不是真实卖出证明。

当前唯一闭环总PNL略正的 `watched_wallet_confirmed_entry_control_v1` 只有 +4.83U，median仍负，去最好3笔后变成 -29.61U，**不能支持wallet alpha**。

历史最漂亮的 v22 更说明问题：原始约 `+7.32M U`，但单一token占正token收益 **94.14%**，移除最佳token后直接变成约 `-232.7k U`，移除前三token约 `-554.7k U`。所以“账户总PNL很漂亮”已经被实际数据推翻为不可靠晋级依据。

因此本R2结论非常明确：

**BLOCK ALPHA / BLOCK CORE PROMOTION / BLOCK LIVE。**

但这**不等于 BLOCK 所有小额研究Paper**。

---

## 二、对其他R1至少三项明确反驳/限定

**对 ADVERSARIAL_RISK：部分赞成，但不同意把晋级反证提前变成候选部署前置。**

我赞成它要求token去重、regime、成本、延迟、placebo和execution plausibility。但这些是判断“这个机制已经赚钱”的必要证据，不应全部变成5U研究Paper的部署门。

例如要求额外恶化2–5%退出价格、+5/+15/+30秒延迟后仍盈利，适合作为**promotion stress test**；若要求每个新L0机制在部署前都满足，会导致项目根本无法产生新前向证据。

所以：

> `BLOCK PROMOTION ≠ BLOCK EXPERIMENT`.

**对 CAUSAL_STATISTICS：赞成机会级统计，但反对为了新Paper先建设一套重型新因果基础设施。**

它要求下降到 `token × canonical pool × cohort/opportunity × time block` 作为主要统计单位，这个方向正确。但项目现有token/cohort、activation、strategy treatment已经足以支撑第一阶段严格配对。

如果为了部署一个5U L0假设先重构完整 `opportunity_id` 基础设施，属于研究工具压过业务目标。应让Codex尽量**复用已有cohort/token/activation键**；缺少的统计映射可以离线完成。

**对 MICROSTRUCTURE：赞成真实金额流比count更有经济意义，但不同意把它提升成全部候选的必需输入。**

实际免费采集存在signature截断、协议/链覆盖、窗口完整性等限制。若强制“只有amountful flow才能交易”，会让大量L0假设无法形成分母。

正确分层应是：

- L0策略只能声称L0机制；
- amountful flow可作为更高质量独立候选/增强；
- 绝不能把tx count叫资金流；
- 也不能因为没有金额流就禁止所有L0 Paper。

---

## 三、16机制逐项R2裁决

| 草案机制 | R2裁决 | 小额Paper | 核心理由 |
|---|---|---|---|
| `l0_continuation_failure_candidate_v1` | **保留，高优先级** | **YES** | 当前91个闭仓交集candidate相对control约+21.79U，只是少亏且双方仍巨亏；正适合继续严格前向验证“早结束失败尝试” |
| `l0_profit_lock_candidate_v1` | **退出最终核心名单，保留现有负对照** | 不新增 | 当前59配对约 **-62.54U**；不能因为机制名字合理继续优先资源。既有策略/历史保留 |
| `observed_cycle_reset_reacceleration_v1` | **保留** | YES，条件型 | 真正不同的episode状态转换；但80帧/20分钟覆盖限制必须进入coverage denominator |
| `volatility_scaled_depth_flow_momentum_v1` | **保留但降级命名/解释** | YES | 若“flow”只是聚合量代理，应明确叫pressure/activity proxy，不能声称真实资金流 |
| `experiment_participation_candidate_v1` | **保留，链/协议条件型** | YES | 地址扩散是真实不同机制；地址≠人，且输入完整性有限 |
| migration amount absorption | **保留，条件型** | YES | 精确migration + 已解析amount具有行为独立性；只在真实支持协议/链上运行 |
| `clone_liquidity_leader_v1` | **保留，高优先级** | YES | 同题材冻结候选集、事前选leader，天然提供竞争对照；不需要新外部请求 |
| `observed_set_relative_resilience_candidate_v1` | **保留，高优先级** | YES | 与绝对momentum真正不同；只能称observed-set relative，不能称全市场regime |
| 突破后接受 | **保留，新机制** | YES | “位移后新价区被接受”不同于单纯持续斜率；必须两份有意义间隔的独立帧 |
| 窄幅压缩释放 | **保留但与cycle严格分界** | YES | 只保留“第一冲击前的压缩→释放”；若已经发生首波再压缩，则归cycle reset，禁止复制ID |
| 回测区域承接 | **不作为全新机制注册** | 复用旧family | 与 pullback/reclaim/failed-breakout-reclaim高度同质；应归并为一个“retest/reclaim”家族 |
| 抛压减弱反弹 | **保留但先降低语义强度** | **SHADOW→5U** | sell-count share不是sell amount；只能叫“卖出活动占比减弱”，数据完整后再Paper |
| 双次下探吸收 | **删除/并入retest-reclaim** | NO新ID | 两次低点+收复本质是更具体的reclaim形态，单独注册容易形成pattern proliferation |
| 流动性先增后重估 | **保留，但先Shadow** | 条件YES | provider liquidity USD可能与价格机械耦合；必须先证明price-flat阶段的增量不是报价构造效应 |
| 首冲后缩量再启动 | **并入cycle reset/reacceleration** | NO新ID | 与“首波深重置后二次启动”行为近乎同族，只是对reset定义增加缩量条件 |
| 阶梯式趋势持有 | **保留为独立exit/hold treatment** | 5U paired YES | 与entry alpha分开；conditional runner已有负证据，因此必须同entry配短持control，且限制尾部暴露 |

因此我不支持根草案直接 **8+8=16个全部独立ID**。

建议实际压缩到大约 **12–13个机制家族**，其余作为旧family的条件/子状态，不制造策略数量幻觉。

---

## 四、建议最终候选骨架：13个真正不同的机制

我建议Codex最终综合时优先保留：

1. continuation-failure exit
2. pre-impulse compression → release
3. post-impulse reset → reacceleration
4. breakout → price-level acceptance
5. failed-breakout / retest → reclaim
6. sell-activity weakening → rebound
7. volatility-normalized momentum
8. participant expansion
9. migration amount absorption
10. clone liquidity leadership
11. observed-set relative resilience
12. liquidity-leading repricing
13. stair-step continuation hold

`l0_profit_lock` 不删除历史、不停止现有证据，但**从优先终极候选退为现有negative/control treatment**。

钱包信誉、完整creator/funding graph、KOL、多源事件等继续作为条件型研究储备；目前不应该为了凑“终极16”强塞进去。

---

## 五、几项实施前必须修正的语义，不需要大重构

第一，**独立帧必须有时间意义**。当前系统有过0/10/15秒密帧和重复帧问题。新序列策略不能把同一市场瞬间的重复provider刷新当“两次确认”。具体最小跨度由Codex按现有采样合同冻结，但必须是positive elapsed time且identity/freshness有效。

第二，**80帧/20分钟是硬观察窗口，不是无限历史**。超过窗口才成立的阶梯、双底、重启动作不能用后来的历史补回来；结果应记coverage miss。

第三，**liquidity USD不是LP净流入**。“流动性先增”如果只是价格上涨使美元TVL增加，就没有独立信息。没有reserve/native-liquidity可分解证据时，应先Shadow验证其机械相关程度。

第四，**sell-count下降不是卖压金额下降**。因此“抛压减弱反弹”第一版只能使用活动结构措辞，不能称seller absorption。

第五，**重入必须依赖已有正确episode边界**。没有就不做“无限二次、三次重入”；一次新episode一次资格即可。

---

## 六、BONK日期冲突：R1_EXTERNAL 的 2022-12-08 不应继续传播

`R1_EXTERNAL_RESEARCH.md` 写 BONK `2022-12-08`，但没有给出可核验的原始依据，只留了Chat内部citation和一个二级行情页。

完成后的 `EXTERNAL_EMPIRICAL_EVIDENCE.md` 改为引用CoinGecko直接研究页；我又直接打开该页面核验。CoinGecko明确写：

- BONK **launch：2022-12-25**
- 2023-01-02为launch后第8天，+305.8%
- 2023-01-05为第11天阶段高点
- 另明确写首次airdrop announcement是 **2022-12-10**。citeturn466003view0

所以本轮应冻结：

**BONK launch = 2022-12-25（按当前直接核验来源口径）；2022-12-10可称首次airdrop announcement；2022-12-08从当前证据中删除/标记未证实。**

不要把R1里的Chat citation继续当URL证据。

---

## 七、小额Paper到底允不允许？

**允许，但必须准确命名：`PROCEED_BOUNDED_RESEARCH_PAPER`。**

允许的理由不是它们“很可能赚钱”，而是：

- 有明确且行为不同的假设；
- 使用决策时已有信息；
- 没有历史赢家回填；
- 不需要新高成本数据；
- 可以形成失败样本；
- 5U与最多4仓把机会成本/资本风险限制住；
- 旧策略和历史全部保留；
- 不重置账户；
- 能在新frontier形成真正新的out-of-selection证据。

以下原因**阻止盈利宣称，但不阻止5U候选部署**：

- 只有1.29h；
- n高度相关；
- 尚无跨日期/regime稳定性；
- 去极值不稳；
- 当前普通Paper不是实盘可实现报价；
- 多重选择严重；
- outcome右删失；
- 部分chain/input覆盖不足。

而以下原因才应**直接阻止某候选部署**：

- 使用未来数据；
- 无法绑定正确原池/token/episode；
- 实际所需输入当前根本不存在，却拿代理冒充；
- 规则与现有策略行为完全等价；
- 会新增明显阻塞持仓/退出的资源工作；
- 需要当前不存在的重入/第二BUY账本语义却假装已支持；
- 数据缺失会被当成0/安全/失败；
- 需要事后选择leader、低点、峰值或赢家。

这是R2最重要的区分。

---

## 八、最终R2裁决

**BLOCK_ALPHA_PROMOTION = YES**
**BLOCK_LIVE = YES**
**BLOCK_SMALL_RESEARCH_PAPER = NO**
**ALLOW_BOUNDED_5U_PAPER = YES，对上述合格机制**
**RESET_EXISTING_HISTORY/ACCOUNTS = NO**
**DELETE_OLD_STRATEGIES = NO**

对根草案的建议是：**不要部署16个名字，部署约12–13个机制家族；等价的删并，输入不足的Shadow/条件化，明确有新行为且零新增网络成本的5U Paper。**

尤其不要因为当前统计整体很差而停止实验，也不要因为某机制在1.29小时内略少亏就把它叫alpha。

目前最值得优先花资源的是：

**continuation-failure、breakout acceptance、compression/release、cycle reset/reacceleration、retest/reclaim、clone leadership、relative resilience。**

参与扩散、migration amount、sell-activity rebound属于第二梯队；liquidity-leading和stair-step先采用更严格的Shadow/paired设计。

最终由Codex独立裁决与实现；本R2没有写入任何运行状态。
