# ROUND2 六个候选轴的 current-effective 去重

只读源码审查，针对 `R2_PROPOSALS.md` 的 8/2/3/4/5/6。依据已冻结当前 214 合同、`EFFECTIVE_POLICY_CORRECTIONS.md` 及当前 revision → dispatcher → settlement 路径；未重查生产数据库、运行统计、网络或测试，未修改应用。源码存在不等于已部署新改动、输入自然覆盖或 alpha。

## 简洁裁决

| 候选轴 | 与当前已有机制关系 | 可算新增的最小行为差异 | 裁决 |
|---|---|---|---|
| **8 下行冲击修复** | `fast_stop_reclaim_v1`、`experiment_panic_reclaim_candidate_v1` 已覆盖止损后收复及无需先持仓的恐慌修复；`experiment_pullback_reclaim_candidate_v1` 另有首涨后回撤收复 | 必须明确“冲击发生当时冻结参考、后续低位稳定、完整参考位收复”的独立事件状态，不能只改收复比例/等待秒数 | **高重复风险，优先复用；普通‘下跌后涨回来’不新增** |
| **2 慢稳定持有许可** | `finalist_progress_clock_v1` 已按经济进展续时钟；`earn_the_hold_v1` 及 paired/突破派生已有首次持仓资格；190/191 有十分钟经济复核 | 在无进展 deadline 到达时，依据多帧小改善/liq留存/活动不恶化，只给予一次有界延期；并非每次小涨永久重置 | **有条件新增**；没有一次性许可状态就只是 clock 调参 |
| **3 活动边际响应耗尽** | `finalist_activity_failure_v1` 已是活动增加而价格、经济值下降；`price_to_flow_fragility_v1` 已是 actual-flow 不支持涨价，但输入与条件不同 | 活动上升、单位时间价格响应从正转近零、卖方结构增强，允许在尚未跌价时触发 | **与旧策略不完全等价，但与候选6高度相交**；不宜宣称两个独立机制 |
| **4 利润回吐持续时间** | `finalist_profit_budget_v1` 已是净利润高水位回吐 + 两坏帧；通用 trailing 是幅度触发；192 L0 锁利有已知回本 flag 断路 | 固定利润边界下的真实 observed-time 驻留，恢复即取消，缺流/换源不累计；明确边界是否冻结、何时冻结 | **有条件新增**；两帧改成三帧或改回吐百分比不算新 |
| **5 partial 后 runner 重新资格** | **125 已在真实回本 partial 后重置高点**；`executable_recovery_decay_v1` 已按 amount epoch 重置峰；conditional runner 已决定首次部分卖还是全卖 | 每次约定的真实 partial 后建立余仓专属资格 epoch；限定期间必须有新的余仓经济改善和原池留存，否则清余仓 | **资格再审是新点；partial确认/高点重置不是新点**。必须配独立、同partial规则的 baseline |
| **6 卖笔扩张而价稳** | 当前8个 balanced-harvest V002 槽已有 15分钟后 buy_ratio<.45 的单帧退出；watched-wallet / creator 分配退出依赖真实身份/金额，不等于 count proxy | 显式买优势→连续卖优势的状态转移，同时价格/经济值不进展，而非持有到某分钟后看一次比例 | **有条件新增，但优先与3合并设计**；单帧卖占优或改 .45 门槛已等价 |

没有发现这六条完整提案均已由某个现行 ID 原样实现；但它们也绝不是六个全新独立机制。最明显的已有等价子行为是“跌后反转”“低买占比退出”“partial后重置高点”“利润回吐两帧退出”。

## 8：已有冲击/收复合同不能略过

`fast_stop_reclaim_v1` 当前不在 evidence-extension 替换名单中，仍路由 `capital_entry.opportunity_signal`。实际规则：

- 当前资金期、同 Token/原池存在**其他策略**真实自然 hard_stop；`closed`，无已记录 contamination / correction / credit，且有截止当时可得的 stop SELL、mark 和 post-confirmation liquidity。不是 writeoff、不是事后合成止损。
- 距 stop 60～600 秒（上界不含）；stop 后至少4帧、跨度≥30秒、相邻 gap≤45秒；末3价严格递增。
- 当前价≥`max(stop_price×1.08, prior_entry_price×0.90)`，当前 liquidity≥stop liquidity×0.80。确认后仍走后帧执行。

定位：`capital_policies.py:206`，`capital_entry.py:375`，`store.py:26421`。

`experiment_panic_reclaim_candidate_v1` / control 不需已有仓位或止损：独立观察≥15秒间隔、最近300秒序列、gap≤90秒，池龄≥900秒、liquidity≥5000、buy_ratio≥.55；中途低点≤首价80%，低点后至少两帧，末价较低点≥1.05且末两价向上；candidate 额外窗口 liquidity 留存≥.8。这是已经存在的市场冲击→修复家族。`experiment_pullback_reclaim_candidate_v1` 则要求先涨≥15%、回撤到峰85%～95%、反弹≥5%且重回峰95%以上，属于先涨后回撤家族。定位：`forward_patterns.py:285,314,323`。

因此候选8若只把 `0.9×entry` 改成“完全收复”、或给 panic_reclaim 换一个阈值，是参数变体。可研究的真正差异只能是**冲击事件一经观测就冻结前参考与低位，之后不能随滑动窗口重选锚点**，并明确后续“低位稳定”是持久状态而非末两帧向上。是否值得独立账户取决于冻结状态产生不同可比较机会，不因它名字不同就通过。

现有输入：同源原池 price/liquidity、observed/ingested/recorded、既有有界历史；若沿用 fast-stop 还需要已实现 stop 的 entry/stop quote、liq、trade/mark ID。不能用日后止损、全路径最低点或固定 +5m 结果作为入场输入。

## 2：一次有界许可与已有资格/时钟的区别

`finalist_progress_clock_v1`：净经济值=`已实现净回款+当前余仓扣卖出摩擦回收值`；较已接受 progress_value 改善≥stake×1%就更新 progress_at；连续180秒未达到新进展则退出。帧间≥5秒、gap>60秒/换 provider 重置，帧龄≤15秒。它不检查活动/liq健康后授予**仅一次**延期。定位：`research_finalists.py:56,149,183`。

`earn_the_hold_v1`、`paired_earn_the_hold_candidate_v1`、`sustained_breakout_earn_hold_v1`：入场后60～120秒考察 value_ratio≥1、price_return≥0、effective_depth_ratio≥.9、actual net_quote_flow≥0；满足后 `EARNED_HOLD` 持续成立，不再反复评估资格，失败到 deadline 则退出。它需要实际金额 flow/depth，不能用 L0 count 或 USD liquidity 偷换；不是候选2的尚未完全回本但健康的小幅改善延期。`high_recall_exit_pipeline_v1` 的首段是相同 probation。定位：`capital_exits.py:46,312,751`。

190/191 `l0_continuation_failure_candidate/control` 的 current V002 已取消旧60/120秒狭窄检查；现为共同10分钟经济值未转正退出、30分钟上限，candidate另加两帧L0亏损恶化。125的30分钟复核检查**实际回款是否覆盖本金**。它们都不是一次小幅改善许可，不应拿旧说明去重。

现有输入：held L0、当前经济值、stake、活动字段、原池/provider/timestamps；新增只是常数大小状态 `permission_used / expires_at / accepted_baseline`。有效性未知；小改善不得反复延期绕过 max_hold、硬止损或风险退出。

## 3 / 6：方向不同于上一轮，但两提案之间可能重复

上一轮 `finalist_activity_failure_v1` 要求**连续两次 price 与经济值下降，buy_ratio 上升且 m5 volume 每次>前帧1.02**。候选3/6则允许价稳、买占比向卖方移动，方向不同，不能说上一轮已等价覆盖。`finalist_depth_divergence_v1` 是跌价/经济值下降且报告liq连续+1%，同样不是该方向。定位：`research_finalists.py:187–206`。

已有聚合卖方退出不可漏掉：以下8个 current V002 槽共享 `broad_balanced_harvest_flow_exit_v2`，持有≥15分钟、当前 buy_ratio<.45 即触发 `market_mark_buy_ratio_faded`；无需前态买优势、连续变化、价稳、量增加或经济停滞：

`canonical-0df3639e1824ad0f`、`canonical-22dbe223b3814f7f`、`canonical-2d3874b5b4dfe162`、`canonical-744153cee3d16c08`、`canonical-83fdc6be4ed5e6bf`、`canonical-d276043eb5aa27c2`、`canonical-d785aa5181f97422`、`canonical-eaaf188e7835376f`。

定位：`revision_main_extensions.py:50,87`，`store.py:33754`。**仅把15分钟改早、.45改.50不构成新行为轴。**

`price_to_flow_fragility_v1` 要求60秒价格涨≥30%、actual net flow≤0、有效深度下降≥10%、有效广度下降≥25%、top3买入金额集中≥70%，不是 m5 volume 边际响应。`creator_early_holder_distribution_v1` 与 `watched_wallet_distribution_candidate_v1` 使用实际 creator/早期持有人金额，或同 watched signer 先BUY后SELL，再结合结构/L0恶化；不能因都有“分配”字样认为等价，也不能把其身份/金额逻辑改称 count 已接通。定位：`capital_exits.py:67,447`，`wallet_observer_experiments.py:246`。

3与6互相去重：若“结构向卖方转”最后也定义为跨越买卖优势，3往往只是6再加 volume 上升、价格斜率耗尽。优先冻结一个基础状态机；只有要直接检验额外活动响应条件的边际效应时才做同机会消融，不能将二者计作独立的两种经济发现。

现有输入：同源原池 price、net economic value、m5 volume/buys/sells、真实观察时间。价格响应应按实际间隔归一化，m5差分只称**重叠滚动窗口代理**，不能称新增成交额或净流。至少3帧足以表达两段斜率；买优势→卖优势的前态必须实际观察并冻结，不能用末帧倒推。

## 4：duration 不是 bad-frame 数量换名

`finalist_profit_budget_v1` 当前 running net profit≥stake20%后，profit≤已知 peak 的50%算坏帧；两坏帧退出，恢复清 streak。它已经存在“回吐+持续确认”，**不是瞬时幅度止盈**。minimum_span=5秒、maxgap=60秒，因此两坏帧并非一个固定真实持续时间。普通 `market_mark_trailing_exit` 才是达到激活收益和回撤幅度后立即触发。定位：`research_finalists.py:56,174,187`，`store.py:33705`。

新duration只在这些规则被写清时成立：边界何时冻结/是否随已知高点抬升；首次越界何时开始；恢复后取消而非暂停；断流/换源使驻留证据重置；用观测时间累计而不是调用次数；到预算后还要下一有效原池帧成交。**它不能让缺观测本身消耗危险驻留时间。**

192 `l0_profit_lock_candidate_v1` current V002 的25%半卖+两帧恶化不是 duration；L0 adapter 未派生 cost_covered，principal flag 仅125专用结算路径置位，仍有已识别不可达门。不得当已成功运行的 duration 对照。金额版 `failed_continuation_profit_lock_v1`/paired candidate 的 adapter 会由实际净回款派生 recovered，和 L0192 不是同一条断路；它采用两帧 actual-flow/结构恶化，亦无固定驻留计时。定位：`store.py:31635,32909`，`capital_context.py:185`，`l0_experiments.py:211`，`capital_exits.py:374`。

现有输入：经济值、stake、provider/pool/timestamps；不需要新行情源。若改用“曾略盈利”而非20%激活，会同时改变 activation 和 duration，必须在对照解释中分开，不能把差异全归时间。

## 5：已有 partial 真实确认/高点重置，新增只能是余仓资格再审

125 `broad_principal_lock_runner_v1` current V002：经济收益40%时卖75%；actual cumulative net proceeds≥原stake才置 `principal_recovered`，同一次真实 partial settlement 将 `highest_signal_price_usd=post_price`、`highest_economic_value_usd=post_fill_economic_value`，不拼 partial 前高点。**这一因果重置已经存在。** 之后没有“在partial后限定时间内赚得新的余仓高点”的资格状态。定位：`strategy_revisions.py:343`，`store.py:32645,32889–32925`。

`experiment_conditional_runner_candidate_v1` / `serial_conditional_runner_v1` 在首次TP（经济收益12%）用两帧 buy_ratio≥.55、liq/entry_liq≥.8 决定卖一半，否则全卖；只有 `tp_index==0` 才做这个判断，第二档经济收益30%清剩余。它是**首次留下runner**，不是actual partial之后重新资格。定位：`forward_patterns.py:53,89,347`，`store.py:33781`。

`high_recall_exit_pipeline_v1` 的 HARVEST_PENDING 会核验实际 sold_fraction 与 realized_proceeds 上升并回本，随后 HARVESTED 监控两帧 dead-wave；没有partial后期限内必须再创新高的要求。`executable_recovery_decay_v1` 则已按真实 amount_epoch/unit 重置 running peak，再看1.4×激活和15%回撤，亦非期限资格；其 amount-specific quote 合同不能扩散为本轮普通Paper的额外门。定位：`capital_exits.py:678,814,889`。

可复用的现有输入/实现边界：真实 settlement 的 fill_id、completed_at、remaining_quantity_tokens、allocated_cost、realized_proceeds、post_price，及后续新鲜同源原池L0；`capital_exit_state_json`可存专属epoch，不需扫描成交表找partial。epoch 必须由**actual fill**启动，不能由TP trigger或pending mark启动。余仓改善需用固定余量下的净回收值，不能把旧已实现回款上升、数量变化或partial前峰拼成新进展。多次partial是重置、只考察第一次、还是限次数，需要合同先明确。

本次建议：优先保留2/4/5的真正状态差异；3/6按一基础机制与可选消融处理；8先按已有fast-stop/panic-reclaim复用核对。它们均仍是假设，不因代码可实现就增加验证结论或必须注册的数量。
